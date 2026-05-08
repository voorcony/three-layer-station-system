# 单位商品 — Shopify 商品页面设计指南 (v3)

## 概述

三层站群 v3 使用**单一固定单价商品**（如 $99 家具）作为支付匹配单位。客户不会直接访问这个商品的 Shopify 页面——他们通过 A 站落地页完成下单流程。但 Shopify 商品页面在以下场景可能会被看到：

- 客户手动查看 Shopify 后台订单
- 偶然的 SEO 访问（建议隐藏或 noindex）
- 未来拓展 B 站直接销售

---

## 设计原则

1. **真实在售** — 这个商品必须是真实可发货的（e.g., 家具、日用品）
2. **简单低调** — 不要过度设计，不需要奢华感
3. **单价匹配** — 价格固定，便于计算

---

## 推荐配置

### 商品标题
```
Premium Furniture Piece — Solid Construction
```
或者更通用的 `Standard Item` / `Unit Item`

### 商品图片
- 清晰的产品实拍图（白底或实景）
- 不要过度修饰，真实即可

### 描述（简洁版）
```
A premium quality furniture piece, crafted with care. 
Sold as individual unit. 
Contact us for custom orders or bulk pricing.
```

如果不想让客户注意到这个商品，也可以留空或简单一句话。

### SEO 设置

```yaml
Search engine listing preview:
  Page title: Premium Furniture Piece
  Meta description: (留空)
  URL handle: /products/premium-furniture-piece
```

建议在 Shopify 主题设置中把这个商品从导航/推荐商品中隐藏：

- 不加入任何 collection
- 不在首页展示
- 设置 `robots: noindex`（如果需要）

---

## 为什么不需要精美设计

v3 的支付流程：

```
A站落地页（精美设计） → 客户付款（Shopify checkout 看不到商品页） → 收到真商品
                                                      ↑
                                              客户在 Shopify checkout
                                              只看到结算页面，不是商品页
```

客户体验路径中**不经过** Shopify 商品页，所以这个商品页面本身不需要特别设计。

---

## 多商品方案（未来）

如果想支持多个单位商品（不同品类用不同的单价），扩展方式：

| A站品类 | 单位商品 | 单价 | 适用金额范围 |
|---------|---------|:----:|:-----------:|
| 手表 | Standard Watch Case | $249 | $500-$5,000 |
| 包包 | Premium Bag Pouch | $199 | $400-$3,000 |
| 电子产品 | Tech Accessory Kit | $99 | $200-$2,000 |
| 默认（家具） | Premium Furniture Piece | $99 | $200-$2,000 |

按品类配置 `.env` 或多组环境变量即可。

---

## 注意

- **无需"Luxury Gift Collection"多变体方案** — v3 已弃用
- **无需精美产品页** — 客户看不到，别花时间在上面
- **确保库存充足** — 设为不追踪库存或保持 999+
- **关闭邮件通知** — 如果你不希望客户收到 Shopify 的订单确认邮件，在 Shopify Admin → Settings → Notifications 中关闭
