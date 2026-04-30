# Shopify "Luxury Gift Collection" Product Setup Guide

## Why This Is Needed

The Admin API token is invalid (returns 401 for all API versions and endpoints). Therefore, you need to **manually create** the "Luxury Gift Collection" product in Shopify Admin.

Once created, the system will auto-detect it at startup and use its 20 variants for dynamic pricing.

## Step-by-Step Instructions

### 1. Log into Shopify Admin

Go to: https://147xvt-jc.myshopify.com/admin

### 2. Create a New Product

1. Click **Products** → **Add product**
2. Set **Title** to: `Luxury Gift Collection`
3. Set **Description** to (copy-paste this):

```
# Luxury Gift Collection

Experience the pinnacle of elegance with our Luxury Gift Collection. Each tier is meticulously curated to offer an unforgettable unboxing experience.

## Why Choose Our Gift Collection?

🎁 **Premium Presentation** – Every gift arrives in a handcrafted, piano-finished luxury gift box with magnetic closure and velvet interior.

✨ **Guaranteed Quality** – Each item is inspected and certified before dispatch. Your satisfaction is 100% guaranteed.

🚚 **Express Worldwide Shipping** – Tracked and insured delivery to your doorstep.

🔒 **Secure Payment** – All transactions are encrypted and processed securely.

## The Perfect Gift

Whether it's for a birthday, anniversary, corporate event, or just because — our Luxury Gift Collection makes every occasion special. Choose your tier below and add a personalized message at checkout.
```

4. Set **Media**: Upload a beautiful luxury gift box image. You can find royalty-free images on:
   - Unsplash: Search "luxury gift box" or "elegant gift"
   - Pexels: Similar searches
   - **Recommended**: A dark/black background with gold accents gift box for maximum luxury feel

### 3. Add Pricing Variants

Add these **20 variants** one by one. For each variant:

1. Scroll to **Pricing** section
2. Click **Add variant** (you may need to add an option first, e.g., "Tier")
3. For each variant, set:
   - **Option value**: `$100 Tier`, `$200 Tier`, etc.
   - **Price**: The corresponding dollar amount
   - **SKU**: `LUXURY-100`, `LUXURY-200`, etc. (optional but recommended)
   - **Inventory**: Check "Track quantity" and set to a high number (999)

Full variant list:

| # | Option Value    | Price  |
|---|-----------------|--------|
| 1 | $100 Tier       | $100   |
| 2 | $200 Tier       | $200   |
| 3 | $300 Tier       | $300   |
| 4 | $400 Tier       | $400   |
| 5 | $500 Tier       | $500   |
| 6 | $600 Tier       | $600   |
| 7 | $700 Tier       | $700   |
| 8 | $800 Tier       | $800   |
| 9 | $900 Tier       | $900   |
|10 | $1000 Tier      | $1000  |
|11 | $1100 Tier      | $1100  |
|12 | $1200 Tier      | $1200  |
|13 | $1300 Tier      | $1300  |
|14 | $1400 Tier      | $1400  |
|15 | $1500 Tier      | $1500  |
|16 | $1600 Tier      | $1600  |
|17 | $1700 Tier      | $1700  |
|18 | $1800 Tier      | $1800  |
|19 | $1900 Tier      | $1900  |
|20 | $2000 Tier      | $2000  |

### 4. Set Product Status

- Set **Status** to **Active** (so it's visible to the Storefront API)

### 5. Save the Product

Click **Save**. After saving, note down the **variant IDs** from the URL when editing each variant (e.g., `gid://shopify/ProductVariant/123456789`).

Alternatively, they'll be auto-detected by the system.

### 6. Verify Auto-Detection

Once saved, the system will automatically detect the product on next restart. To verify:

1. Open the admin dashboard: http://43.154.181.44/admin/login
2. Login with: `admin` / `admin123`
3. Click "🔄 Refresh Products" in the sidebar
4. If successful, you'll see a green toast: "Shopify products refreshed!"
5. New orders will now use the matching variant from $100-$2000 range

Alternatively, you can trigger the refresh via API:
```bash
curl -X POST http://43.154.181.44/api/admin/refresh-shopify-products \
  -H "Authorization: Basic $(echo -n 'admin:admin123' | base64)"
```

## Verify It's Working

1. Create a test order for a $750 watch:
```bash
curl -X POST http://43.154.181.44/api/orders \
  -H "Content-Type: application/json" \
  -d '{
    "product_name": "Test Watch",
    "price": 750,
    "customer_name": "Test User"
  }'
```

2. The response will show the selected variant — it should pick "$800 Tier" ($800 >= $750, closest match)

3. Open the admin dashboard to see the order with real product mapping
