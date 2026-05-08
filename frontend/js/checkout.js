// js/checkout.js — Shopify Checkout Module
// Delegates all checkout logic to B站 API (43.154.181.44)

// B站 API endpoint — FastAPI on B站 server handles all Shopify logic
const B_STATION_API = 'http://43.154.181.44';

/**
 * Submit an order to B站 for Shopify checkout processing.
 * The B站 FastAPI handles: order creation in WooCommerce → cover product matching → 
 * Shopify cart creation → discount code generation → checkout URL return.
 */
async function submitOrderToBStation(sessionId, totalPrice, phone, items) {
  const payload = {
    session_id: sessionId,
    total_price: parseFloat(totalPrice),
    phone: phone,
    items: items.map(item => ({
      product_name: item.productName,
      variant_summary: item.variantSummary || '',
      price: item.price,
      sku: item.sku || ''
    }))
  };

  try {
    const resp = await fetch(`${B_STATION_API}/api/create_checkout`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    
    if (!resp.ok) {
      throw new Error(`B站 API returned ${resp.status}`);
    }

    const data = await resp.json();
    
    // B站 returns variant info; try to get checkout URL if available
    const checkoutResp = await fetch(`${B_STATION_API}/api/checkout/${sessionId}`, {
      method: 'POST'
    });

    if (checkoutResp.ok) {
      const checkoutData = await checkoutResp.json();
      if (checkoutData.checkout_url) {
        return checkoutData.checkout_url;
      }
    }

    // Fallback: use Shopify store URL with session param
    return `https://147xvt-jc.myshopify.com/?session_id=${encodeURIComponent(sessionId)}`;
  } catch (e) {
    console.warn('B站 API error:', e);
    return `https://147xvt-jc.myshopify.com/?session_id=${encodeURIComponent(sessionId)}`;
  }
}

// Expose for use in app.js
window.submitOrderToBStation = submitOrderToBStation;
