# Three-Layer Station System v3 (三层站群支付系统)

**v3.0.0** | A premium multi-layer payment matching system — maps A站 orders to Shopify checkout via quantity + discount matching.

> **Core idea**: A站 sells high-value items ($200-$2,000). 普货站 matches the price by purchasing multiple units of a real Shopify product + a one-time discount code. Customer pays the correct amount and receives the A站 item.

---

## Architecture

```
A站 (Real Storefront)
├── 真实展示商品 (手表/包包/电子产品等)
├── 客户下单 $XXX 金额
├── 客户被提前告知: "你可能在结账页面看到不同的商品组合，价格完全一致"
└── 跳转到普货站创建的 Shopify Checkout

普货站 (Price Matching Bridge)  ←  本系统
├── 接收 A 站订单金额
├── 计算: quantity = ceil(price / UNIT_PRICE)
├── 计算: discount = (quantity × UNIT_PRICE) - price
├── 通过 Shopify Admin API 创建一次性折扣码
├── 通过 Shopify Storefront API 创建 Cart (quantity items + discount code)
└── 返回 checkoutUrl → 客户跳转付款

Shopify / B站 (Payment Channel)
├── 在售真实商品 (如家具 $99/件)
├── 客户支付: quantity × $99 - discount = A站价格 ✓
├── 订单完成 → Webhook 回传单号
└── 本地系统收到单号 → 给客户发A站真货
```

### Example Flow

| A站订单价 | 匹配逻辑 | 客户付 | 客户收到 |
|:---------:|:---------|:------:|:--------:|
| $850 | ceil(850/99)=9件 → $891 - $41(discount) | **$850** | A站手表 ✓ |
| $200 | ceil(200/99)=3件 → $297 - $97(discount) | **$200** | A站手表 ✓ |
| $1,500 | ceil(1500/99)=16件 → $1,584 - $84(discount) | **$1,500** | A站手表 ✓ |

---

## Key Components

| Module | File | Purpose |
|--------|------|---------|
| **Main API** | `app/main.py` | FastAPI app, order CRUD, webhook handling |
| **Storefront Client** | `app/shopify.py` | Shopify Storefront API — cart creation |
| **Admin Client** | `app/shopify_admin.py` | Shopify Admin API — price rules + discount codes |
| **Database** | `app/database.py` | SQLite — order storage |
| **Models** | `app/models.py` | Pydantic request/response models |
| **Landing Page** | `app/templates/order.html` | A站风格落地页模板 |
| **Admin Dashboard** | `app/templates/admin_orders.html` | 订单管理后台 |

---

## Quick Start

### Prerequisites

- Python 3.10+
- Shopify store with **Storefront API token** + **Admin API token** (with `write_discounts`)
- Server with public IP

### Installation

```bash
git clone https://github.com/voorcony/three-layer-station-system.git
cd three-layer-station-system

pip install -r requirements.txt

cp .env.example .env
# Edit .env:
#   SHOPIFY_STORE=your-store.myshopify.com
#   SHOPIFY_STOREFRONT_TOKEN=your_storefront_token
#   SHOPIFY_ADMIN_TOKEN=shpat_...  (with write_discounts scope)
#   UNIT_PRICE=99
#   UNIT_VARIANT_GID=gid://shopify/ProductVariant/xxx

uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
```

### Shopify Admin API Token Setup

1. **Shopify Admin → Settings → Apps and sales channels → Develop apps**
2. Create or select your Custom App
3. **Configuration → Admin API integration**
4. Grant at least: `write_discounts`, `read_discounts`
5. **Save** → copy the `shpat_...` token
6. Set `SHOPIFY_ADMIN_TOKEN` in `.env`

### Shopify Product Setup

1. Create a **single product** in your Shopify store (e.g., "Premium Furniture Piece")
2. Set **price** to your `UNIT_PRICE` (e.g., $99.00)
3. Set **inventory** to a high number (999)
4. Get the **variant GID**:
   ```bash
   curl -X POST https://your-store.myshopify.com/api/2024-10/graphql.json \
     -H "X-Shopify-Storefront-Access-Token: $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"query":"{ products(first:5) { edges { node { id title variants(first:10) { edges { node { id title price { amount } } } } } } } }"}'
   ```
5. Set `UNIT_VARIANT_GID` in `.env`

---

## API Endpoints

### POST /api/orders

Create an order. Returns a landing page URL.

```json
{
  "product_name": "Rolex Submariner",
  "product_spec": "Black dial, steel bracelet",
  "product_image_url": "https://...",
  "price": 850.00,
  "customer_name": "John Doe",
  "customer_phone": "+1..."
}
```

Response:
```json
{
  "order_id": "A3B7X9K2",
  "page_url": "http://your-server/order/A3B7X9K2",
  "unit_quantity": 9,
  "unit_price": 99.00,
  "discount_amount": 41.00,
  "total_price": 850.00
}
```

### POST /api/checkout/{order_id}

Create the Shopify cart with quantity + discount code applied. Returns checkout URL.

### POST /api/webhook/shopify

Receive Shopify order notifications (orders/create, orders/fulfilled).

### Admin Routes

| Route | Description |
|-------|-------------|
| `/admin/login` | Login page (admin/admin123) |
| `/admin/orders` | Order management dashboard |

---

## Order States

```
pending → checkout_created → paid → fulfilled
  ↑                              ↓
  └────────── cancelled ←────────┘
```

---

## Design

The landing page (`app/templates/order.html`) features a luxury brand aesthetic:

| Element | Description |
|---------|-------------|
| **Color Palette** | Deep black `#0c0c0c` + gold `#c5a55a` + warm off-white `#f5f0e8` |
| **Typography** | Cormorant Garamond (serif headings) + Inter (sans-serif body) |
| **Trust Bar** | 4 SVG badges: Secure Checkout, 30-Day Guarantee, Express Shipping, Insured Delivery |
| **Checkout Explanation** | Professional disclosure card explaining the third-party payment flow |
| **CTA Button** | Gold gradient with hover glow effect |
| **Shipping Journey** | 3 SVG illustrations: Quality Inspection, Express Shipping, Joyful Unboxing |

---

## License

MIT
