# Shopify 单位商品配置指南 (v3)

## 概述

三层站群 v3 不再使用 "Luxury Gift Collection" 多变体商品。新方案的核心是一个**固定单价的商品**，通过**数量 + 折扣码**来匹配 A 站订单金额。

### 逻辑

```
A站订单价 = $850
单价商品 = $99.00/件
数量     = ceil($850 / $99) = 9 件
折扣前   = 9 × $99 = $891
折扣     = $891 - $850 = $41
客户付   = $891 - $41 = $850 ✓
```

---

## 第一步：创建单位商品

在 Shopify Admin 中创建一个商品，作为"计价单位"。

1. **Products → Add product**
2. **Title**: `Premium Furniture Piece`（或你喜欢的名字）
3. **Description**: 简洁的商品描述（可选）
4. **Media**: 上传一张真实的商品图片
5. **Price**: `$99.00` ← 这就是 UNIT_PRICE
6. **Status**: Active

这个商品是**真实在售的**——如果你真的卖家具，客户收到这个也完全没问题。

---

## 第二步：获取 Variant GID

用 Storefront API 查询商品变体 ID：

```bash
# 替换为你的 storefront token
TOKEN="your_storefront_token"
STORE="your-store.myshopify.com"

curl -X POST "https://$STORE/api/2024-10/graphql.json" \
  -H "X-Shopify-Storefront-Access-Token: $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "{
      products(first: 10) {
        edges {
          node {
            id
            title
            variants(first: 10) {
              edges {
                node {
                  id
                  title
                  price { amount currencyCode }
                }
              }
            }
          }
        }
      }
    }"
  }' | jq
```

找到你的商品，复制 variant 的 `id`（格式：`gid://shopify/ProductVariant/123456789`）。

---

## 第三步：配置 .env

```env
SHOPIFY_STORE=your-store.myshopify.com
SHOPIFY_STOREFRONT_TOKEN=your_storefront_token
SHOPIFY_ADMIN_TOKEN=shpat_...   # 需要 write_discounts 权限
UNIT_PRICE=99
UNIT_VARIANT_GID=gid://shopify/ProductVariant/123456789
```

---

## 第四步：验证配置

```bash
# 创建一个测试订单
curl -X POST http://localhost:8000/api/orders \
  -H "Content-Type: application/json" \
  -d '{
    "product_name": "Test Watch",
    "price": 850,
    "customer_name": "Test"
  }'

# 响应示例
{
  "order_id": "A3B7X9K2",
  "page_url": "http://localhost:8000/order/A3B7X9K2",
  "unit_quantity": 9,
  "unit_price": 99.0,
  "discount_amount": 41.0,
  "total_price": 850.0
}

# 生成 checkout
curl -X POST http://localhost:8000/api/checkout/A3B7X9K2

# 响应示例
{
  "checkout_url": "https://checkout.shopify.com/...",
  "discount_code": "ORDER-A3B7X9K2",
  "unit_quantity": 9,
  "unit_price": 99.0,
  "discount_amount": 41.0
}
```

---

## 价格匹配表

| A站订单价 | 数量 | 折扣前 | 折扣 | 客户付 |
|:---------:|:----:|:------:|:----:|:------:|
| $200 | 3 | $297 | -$97 | $200 |
| $300 | 4 | $396 | -$96 | $300 |
| $400 | 5 | $495 | -$95 | $400 |
| $500 | 6 | $594 | -$94 | $500 |
| $600 | 7 | $693 | -$93 | $600 |
| $700 | 8 | $792 | -$92 | $700 |
| $800 | 9 | $891 | -$91 | $800 |
| $850 | 9 | $891 | -$41 | $850 |
| $900 | 10 | $990 | -$90 | $900 |
| $1,000 | 11 | $1,089 | -$89 | $1,000 |
| $1,200 | 13 | $1,287 | -$87 | $1,200 |
| $1,500 | 16 | $1,584 | -$84 | $1,500 |
| $1,800 | 19 | $1,881 | -$81 | $1,800 |
| $2,000 | 21 | $2,079 | -$79 | $2,000 |

**注意**: 单价 $99 是测试值。最终可根据 A 站品类选择合适的单位商品价格。理想情况下，`UNIT_PRICE` 应该接近 A 站商品的最低单价，这样 `quantity` 不会太高（建议不超过 20 件，避免客户起疑）。
