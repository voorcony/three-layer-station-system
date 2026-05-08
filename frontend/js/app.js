// js/app.js — Alpine.js Landing App Logic
function landingApp() {
  return {
    // Page config (updated via JSON for same-URL content swap)
    pageTitle: '奢华礼品精选',
    pageSubtitle: '精选高端礼品，为您尊贵的客户',

    // State
    products: [],
    cartItems: [],
    selectedAttributes: {},
    loading: true,
    showCart: false,
    showPhoneModal: false,
    phoneNumber: '',
    isSubmitting: false,
    orderSessionId: null,

    // Init — fetch products from static JSON
    async init() {
      try {
        const resp = await fetch('/data/products.json');
        const data = await resp.json();
        this.products = data.products || [];
        this.pageTitle = data.page_title || this.pageTitle;
        this.pageSubtitle = data.page_subtitle || this.pageSubtitle;
      } catch (e) {
        console.warn('Failed to load products.json, using demo data');
        this.products = this.getDemoProducts();
      } finally {
        this.loading = false;
      }
    },

    // Demo products for standalone testing (no WooCommerce needed)
    getDemoProducts() {
      return [
        {
          id: 1, name: '奢华礼品套装', type: 'variable',
          description: '精选高端礼品套装，多种档次可选',
          images: ['https://via.placeholder.com/400x300?text=Luxury+Set'],
          attributes: [
            { name: '档次', options: ['标准', '豪华', '尊享'], variation: true },
            { name: '包装', options: ['简约', '礼盒', '精装', '限定版'], variation: true }
          ],
          variants: [
            { id: 101, sku: 'SET-A', price: 99, stock_status: 'instock', attributes: { '档次': '标准', '包装': '简约' } },
            { id: 102, sku: 'SET-B', price: 149, stock_status: 'instock', attributes: { '档次': '标准', '包装': '礼盒' } },
            { id: 103, sku: 'SET-C', price: 199, stock_status: 'instock', attributes: { '档次': '豪华', '包装': '礼盒' } },
            { id: 104, sku: 'SET-D', price: 299, stock_status: 'instock', attributes: { '档次': '豪华', '包装': '精装' } },
            { id: 105, sku: 'SET-E', price: 499, stock_status: 'instock', attributes: { '档次': '尊享', '包装': '精装' } },
            { id: 106, sku: 'SET-F', price: 999, stock_status: 'instock', attributes: { '档次': '尊享', '包装': '限定版' } }
          ]
        },
        {
          id: 2, name: '精美手表', type: 'simple',
          description: '经典设计，精工品质',
          images: ['https://via.placeholder.com/400x300?text=Watch'],
          price: 299, stock_status: 'instock', sku: 'WATCH-001'
        }
      ];
    },

    // Variant selection
    selectVariant(product, attrName, option) {
      if (!this.selectedAttributes[product.id]) {
        this.selectedAttributes[product.id] = {};
      }
      this.selectedAttributes[product.id][attrName] = option;
      // Trigger reactivity
      this.selectedAttributes = { ...this.selectedAttributes };
    },

    getSelectedAttribute(productId, attrName) {
      return this.selectedAttributes[productId]?.[attrName] || null;
    },

    getSelectedVariant(product) {
      if (product.type !== 'variable') return null;
      const selected = this.selectedAttributes[product.id];
      if (!selected) return null;

      const variationAttrs = product.attributes.filter(a => a.variation !== false);
      for (const attr of variationAttrs) {
        if (!selected[attr.name]) return null;
      }

      return product.variants.find(v => {
        return Object.entries(selected).every(([key, val]) => v.attributes[key] === val);
      }) || null;
    },

    getSelectedPrice(product) {
      if (product.type === 'simple') {
        return '¥' + (product.sale_price || product.price).toFixed(2);
      }
      const variant = this.getSelectedVariant(product);
      if (variant) return '¥' + variant.price.toFixed(2);

      if (product.variants && product.variants.length > 0) {
        const prices = product.variants.map(v => v.price);
        return '¥' + Math.min(...prices).toFixed(2) + ' 起';
      }
      return '¥0.00';
    },

    getSelectedSummary(product) {
      if (product.type === 'simple') return product.name;
      const selected = this.selectedAttributes[product.id];
      if (!selected || Object.keys(selected).length === 0) return '请选择规格';
      return Object.values(selected).join(' / ');
    },

    canAddToCart(product) {
      if (product.type === 'simple') {
        return product.stock_status === 'instock';
      }
      const variant = this.getSelectedVariant(product);
      return variant !== null && variant.stock_status === 'instock';
    },

    // Cart operations
    addToCart(product) {
      if (product.type === 'variable') {
        const variant = this.getSelectedVariant(product);
        if (!variant) return;

        this.cartItems.push({
          productId: product.id,
          productName: product.name,
          variantId: variant.id,
          variantSummary: this.getSelectedSummary(product),
          price: variant.price,
          sku: variant.sku,
          attributes: { ...this.selectedAttributes[product.id] }
        });
      } else {
        this.cartItems.push({
          productId: product.id,
          productName: product.name,
          variantId: product.id,
          variantSummary: '',
          price: product.sale_price || product.price,
          sku: product.sku,
          attributes: {}
        });
      }
      this.showCart = true;
    },

    removeFromCart(index) {
      this.cartItems.splice(index, 1);
    },

    get cartTotal() {
      return this.cartItems.reduce((sum, item) => sum + Number(item.price), 0);
    },

    get isValidPhone() {
      return /^1[3-9]\d{9}$/.test(this.phoneNumber);
    },

    // Submit order — delegates to B站 API
    async submitOrder() {
      if (!this.isValidPhone || this.isSubmitting) return;
      this.isSubmitting = true;

      try {
        // Generate session ID
        this.orderSessionId = 'ORD_' + Date.now() + '_' + Math.random().toString(36).substr(2, 6).toUpperCase();

        const orderItems = this.cartItems.map(item => ({
          productName: item.productName,
          variantSummary: item.variantSummary,
          price: item.price,
          sku: item.sku
        }));

        // Save locally
        const orderData = {
          session_id: this.orderSessionId,
          phone: this.phoneNumber,
          items: orderItems,
          total: this.cartTotal,
          timestamp: new Date().toISOString()
        };
        localStorage.setItem('pending_order', JSON.stringify(orderData));

        // Submit to B站 → WooCommerce → Shopify
        const checkoutUrl = await window.submitOrderToBStation(
          this.orderSessionId,
          this.cartTotal,
          this.phoneNumber,
          orderItems
        );

        if (checkoutUrl) {
          window.location.href = checkoutUrl;
        } else {
          throw new Error('No checkout URL returned');
        }

      } catch (e) {
        console.error('Submit error:', e);
        alert('提交失败，请稍后重试');
      } finally {
        this.isSubmitting = false;
      }
    }
  };
}
