# 三层站群支付系统 v3 (Three-Layer Station System)

**v3.1.0** | AB站架构 — A站落地页 → B站结算引擎 + WooCommerce + Shopify + 飞书订单同步

> **核心架构**: A站(静态落地页，带字体反爬) → B站(FastAPI结算引擎 + WooCommerce订单) → C站(Shopify结算)，所有订单同步飞书Bitable供运营查看

---

## 系统架构

```
┌─────────────────────────────────────────────────────┐
│              A站 (43.130.2.243)                       │
│  ┌──────────┐  ┌───────────┐  ┌───────────────────┐  │
│  │  Landing  │  │  WooCommerce│  │  Checkout API     │  │
│  │  Page     │──│  (内网8080) │  │  (port 8099)      │  │
│  │  :8091    │  │  产品管理    │  │  → Shopify Cart   │  │
│  └────┬─────┘  └───────────┘  └───────────────────┘  │
│       │                                 ▲             │
│       │ 用户浏览器POST                    │             │
│       ▼                                 │             │
│  ┌──────────────────────────────────────┘             │
│  │ Nginx 反代 (:8091)                                  │
│  │  - 字体反爬 (自定义WOFF2)                             │
│  │  - UA/爬虫检测 → review.html                         │
│  │  - 静态文件强缓存                                     │
│  └─────────────────────────────────────────────────────┘
│                    │
│       HTTPS POST   │  (用户浏览器 → 外网请求)
│                    ▼
┌─────────────────────────────────────────────────────┐
│              B站 (43.154.181.44)                      │
│  ┌──────────────────────────────────────────────┐    │
│  │  FastAPI 结算引擎 (:8000)                      │    │
│  │  ┌──────────┐ ┌─────────┐ ┌───────────────┐  │    │
│  │  │Shopify   │ │Shopify  │ │ 飞书订单同步    │  │    │
│  │  │Storefront│ │Admin    │ │(feishu_sync)  │  │    │
│  │  │Cart创建   │ │折扣码生成 │ └──────┬────────┘  │    │
│  │  └────┬─────┘ └────┬────┘        │           │    │
│  │       │            │             │           │    │
│  │  ┌────▼────────────▼─────────────▼────────┐  │    │
│  │  │  WooCommerce B站 (内网8080)              │  │    │
│  │  │  - WordPress + WooCommerce              │  │    │
│  │  │  - 订单CRUD API (orders-api.php)         │  │    │
│  │  │  - 存储 session_id / phone / items      │  │    │
│  │  │  - 存储 feishu_record_id                 │  │    │
│  │  └─────────────────────────────────────────┘  │    │
│  └──────────────────────────────────────────────┘    │
│                    │                                  │
│                    ▼                                  │
│  ┌──────────────────────────────────────────────┐    │
│  │  Nginx反代 (:80)                               │    │
│  │  - /api/* → FastAPI :8000                      │    │
│  │  - /order/* → FastAPI :8000                    │    │
│  │  - /health → FastAPI :8000                     │    │
│  └──────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────┐
│              C站 (Shopify)                            │
│  ┌──────────────────────────────────────────────┐    │
│  │  store: 147xvt-jc.myshopify.com              │    │
│  │  - Cover Product: Luxury Gift Collection      │    │
│  │  - 20 variants ($100-$2000)                  │    │
│  │  - 按金额匹配对应的变体                          │    │
│  │  - 用户直接Shopify Checkout付款                │    │
│  │  - Webhook回调 → B站更新状态                   │    │
│  └──────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────┐
│              飞书 Bitable (运营端)                    │
│  ┌──────────────────────────────────────────────┐    │
│  │ 订单管理多维表                                  │    │
│  │ 字段: 订单ID / 客户信息 / 金额 / 产品明细 /     │    │
│  │       状态 / Shopify订单号 / 结算链接 / 时间   │    │
│  └──────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────┘
```

### 数据流

```
用户访问 A站 Landing Page
  → 选择产品&变体（可多产品加购）
  → 点「立即结账」
    → 弹窗收集手机号
    → POST /api/create_checkout 到 B站

B站 FastAPI:
  → 生成 session_id (ORD_xxxxxxxx)
  → 通过 orders-api.php 在 WooCommerce B站 创建订单
    → meta_data: _session_id, _customer_phone, _items_json, _total_price, _customer_name
  → 通过飞书API在Bitable创建订单记录
    → 字段: 订单ID, 客户信息, 金额, 产品明细, 状态(Pending), 结算链接
  → 通过 Shopify Storefront API 创建 Cart
  → 返回 checkout_url

用户跳转 Shopify Checkout
  → 付款完成
  → Shopify Webhook 回调 B站 /api/webhook/shopify
    → 更新 WooCommerce B站 订单状态
    → 更新飞书 Bitable 记录 (状态→Paid, Shopify订单号)
```

### 防关联原则

| 要求 | 实现 |
|------|------|
| A站↔B站无服务器直连 | 所有跨站通信通过**用户浏览器端POST** |
| A站域名/服务器独立 | A站43.130.2.243, B站43.154.181.44 |
| WooCommerce不对外暴露 | 仅127.0.0.1:8080内网访问 |
| A站落地页防爬 | 字体反爬+custom WOFF2 + UA检测 |
| 同URL内容替换 | Nginx配置切换/review.html→landing.html |

---

## 目录结构

```
three-layer-station-system/
├── frontend/                     # A站 落地页 (43.130.2.243)
│   ├── landing.html              # 主落地页（多产品+变体）
│   ├── review.html               # 过审用普通页面
│   ├── css/
│   │   └── style.css
│   ├── js/
│   │   ├── app.js                # 购物车+变体选择逻辑
│   │   └── checkout.js           # 结算请求发送
│   ├── data/
│   │   ├── products.json         # 产品数据
│   │   ├── categories.json       # 分类数据
│   │   └── category_*.json       # 分类商品详情
│   └── fonts/
│       ├── anticrawl.woff2       # 字体反爬文件
│       └── b-site.woff2          # 品牌字体
│
├── app/                          # B站 FastAPI (43.154.181.44)
│   ├── main.py                   # FastAPI主服务 (316行)
│   ├── models.py                 # Pydantic模型
│   ├── shopify.py                # Shopify Storefront API (Cart创建+变体匹配)
│   ├── shopify_admin.py          # Shopify Admin API (折扣码管理)
│   ├── wc_api.py                 # WooCommerce API封装 (订单CRUD)
│   ├── sync_feishu.py            # 飞书Bitable同步模块
│   └── __init__.py
│
├── backend-api/                  # A站 Checkout API (43.130.2.243)
│   ├── checkout_api.py           # A站结算API (port 8099)
│   ├── sync_products.py          # 从WooCommerce A站同步产品
│   ├── requirements.txt
│   └── requirements_api.txt
│
├── deploy.sh                     # 部署脚本
├── requirements.txt              # Python依赖
├── .env.example                  # 环境变量模板
├── .gitignore
└── README.md
```

---

## 部署指南

### 前提条件

| 资源 | 说明 |
|------|------|
| 两台Linux服务器 | A站 43.130.2.243 / B站 43.154.181.44 (均为 ubuntu) |
| Shopify商店 | 147xvt-jc.myshopify.com (需Storefront + Admin Token) |
| 飞书自建应用 | 需要app_id + app_secret + Bitable权限 |
| 域名(可选) | cesomail.com (可绑定Cloudflare Tunnel) |

### A站部署 (43.130.2.243)

```bash
# 1. 部署 Landing Page
sudo mkdir -p /var/www/landing
cp -r frontend/* /var/www/landing/
sudo chown -R ubuntu:ubuntu /var/www/landing/

# 2. 配置 Nginx
# 复制 nginx-config/landing 到 /etc/nginx/sites-available/
sudo ln -sf /etc/nginx/sites-available/landing /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

# 3. 部署 Checkout API
mkdir -p /home/ubuntu/landing-backend
cp backend-api/* /home/ubuntu/landing-backend/
python3 -m venv /home/ubuntu/landing-backend/venv
source /home/ubuntu/landing-backend/venv/bin/activate
pip install -r /home/ubuntu/landing-backend/requirements_api.txt

# 4. 创建 systemd 服务
cat > /etc/systemd/system/landing-checkout.service << 'EOF'
[Unit]
Description=Landing Checkout API
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/landing-backend
Environment=SHOPIFY_STORE=147xvt-jc.myshopify.com
Environment=SHOPIFY_STOREFRONT_TOKEN=your_token
ExecStart=/home/ubuntu/landing-backend/venv/bin/python -m uvicorn checkout_api:app --host 127.0.0.1 --port 8099
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now landing-checkout

# 5. 部署 WooCommerce (产品管理)
docker run -d --name mysql-wc \
  -e MYSQL_ROOT_PASSWORD=rootpass \
  -e MYSQL_DATABASE=wordpress \
  -e MYSQL_USER=wpuser \
  -e MYSQL_PASSWORD=wppass \
  -v /var/lib/mysql-wc:/var/lib/mysql \
  mysql:8.0

docker run -d --name wordpress-wc \
  -p 127.0.0.1:8080:80 \
  -e WORDPRESS_DB_HOST=172.17.0.1 \
  -e WORDPRESS_DB_USER=wpuser \
  -e WORDPRESS_DB_PASSWORD=wppass \
  -e WORDPRESS_DB_NAME=wordpress \
  -v /var/www/html:/var/www/html \
  wordpress:latest
```

### B站部署 (43.154.181.44)

```bash
# 1. 部署 FastAPI
sudo mkdir -p /opt/three-layer-stations
cp -r app/* /opt/three-layer-stations/app/
sudo chown -R ubuntu:ubuntu /opt/three-layer-stations/

python3 -m venv /opt/three-layer-stations/venv
source /opt/three-layer-stations/venv/bin/activate
pip install -r requirements.txt

# 2. 配置 .env
cp .env.example /opt/three-layer-stations/.env
# 编辑填入: SHOPIFY_STORE, SHOPIFY_STOREFRONT_TOKEN, SHOPIFY_ADMIN_TOKEN, FEISHU_*

# 3. 创建 systemd 服务
cat > /etc/systemd/system/three-layer-stations.service << 'EOF'
[Unit]
Description=Three-Layer Station System (B站)
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/three-layer-stations
EnvironmentFile=/opt/three-layer-stations/.env
ExecStart=/opt/three-layer-stations/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 2 --log-level info
Restart=always
RestartSec=5
Environment=PYTHONPATH=/opt/three-layer-stations

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now three-layer-stations

# 4. 部署 WooCommerce B站 (订单管理)
docker run -d --name mysql-wc-b \
  -e MYSQL_ROOT_PASSWORD=rootpass \
  -e MYSQL_DATABASE=wordpress_b \
  -e MYSQL_USER=wpuser \
  -e MYSQL_PASSWORD=wppass \
  -v /var/lib/mysql-wc-b:/var/lib/mysql \
  mysql:8.0

docker run -d --name wordpress-wc-b \
  -p 127.0.0.1:8080:80 \
  -e WORDPRESS_DB_HOST=172.17.0.1 \
  -e WORDPRESS_DB_USER=wpuser \
  -e WORDPRESS_DB_PASSWORD=wppass \
  -e WORDPRESS_DB_NAME=wordpress_b \
  -v /var/www/html:/var/www/html \
  wordpress:latest

# 5. 部署 orders-api.php (WooCommerce自定义API)
cp orders-api.php /var/www/html/wp-content/orders-api.php

# 6. 配置 Nginx 反代
cp nginx-config/api-gateway /etc/nginx/sites-available/
ln -sf /etc/nginx/sites-available/api-gateway /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

---

## API 端点

### B站 FastAPI (`43.154.181.44/api/`)

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/health` | GET | 健康检查 → `{"status":"ok","version":"3.0.0","database":"woocommerce"}` |
| `/api/create_checkout` | POST | 创建订单+Shopify结算链接 (核心端点) |
| `/api/webhook/shopify` | POST | 接收Shopify订单回调 |
| `/api/order/{order_id}` | GET | 查询订单状态 |

### POST /api/create_checkout

请求体：
```json
{
  "source": "landing",
  "session_id": "ORD_xxxxxxxx",
  "phone": "13800138000",
  "total_price": 850.0,
  "items": [
    {"name": "高端腕表", "variant": "黑色表盘", "price": 600},
    {"name": "礼品套装", "variant": "豪华版", "price": 250}
  ],
  "customer_name": "张三"
}
```

响应：
```json
{
  "status": "ok",
  "order_id": "ORD_99dbb5c1",
  "checkout_url": "https://147xvt-jc.myshopify.com/cart/c/f5bd32...",
  "total_price": 850.0,
  "items": [
    {"name": "高端腕表", "variant": "黑色表盘", "price": 600},
    {"name": "礼品套装", "variant": "豪华版", "price": 250}
  ]
}
```

### POST /api/webhook/shopify

请求体（模拟测试用）：
```json
{
  "session_id": "ORD_99dbb5c1",
  "shopify_order_id": "12345",
  "status": "paid",
  "customer_email": "test@example.com"
}
```

---

## Nginx 配置

### A站 Landing (43.130.2.243:8091)

```nginx
server {
    listen 8091;
    server_name _;

    root /var/www/landing;
    index landing.html;

    # 反爬检测
    set $bot_detected 0;
    if ($http_user_agent ~* "(facebookexternalhit|Facebot|Meta-ExternalAgent|Googlebot|Bingbot|GPTBot|curl|wget|python)") {
        set $bot_detected 1;
    }
    location / {
        if ($bot_detected = 1) { rewrite ^ /review.html break; }
        try_files $uri $uri/ /landing.html;
    }

    # CDN级缓存
    location /fonts/ { add_header Cache-Control "public, max-age=31536000, immutable"; }
    location /js/     { add_header Cache-Control "public, max-age=3600, immutable"; }
    location /css/    { add_header Cache-Control "public, max-age=3600, immutable"; }

    gzip on;
    gzip_types text/html text/css application/javascript application/json;
}
```

### B站 API Gateway (43.154.181.44:80)

```nginx
server {
    listen 80;
    server_name 43.154.181.44;

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /order/ {
        proxy_pass http://127.0.0.1:8000;
    }

    location /health {
        proxy_pass http://127.0.0.1:8000;
    }

    location /admin/ {
        proxy_pass http://127.0.0.1:8000;
    }

    location /dashboard/ {
        proxy_pass http://127.0.0.1:8086/;
    }
}
```

---

## 飞书 Bitable 订单管理

| 字段名 | 类型 | 说明 |
|--------|------|------|
| 订单ID | 文本 | ORD_xxxxxxxx (session_id) |
| 客户信息 | 多行文本 | 姓名 + 手机号 |
| 金额 | 数字 | 总价 (元) |
| 产品明细 | 多行文本 | JSON: [{name, variant, price}] |
| 状态 | 单选 | Pending / CheckoutCreated / Paid / Cancelled |
| Shopify订单号 | 文本 | 付款后回写 |
| 创建时间 | 日期 | 订单创建时间 |
| 刷新 | 文本 | 预留刷新按钮 |

---

## 环境变量 (.env)

```env
# Shopify
SHOPIFY_STORE=147xvt-jc.myshopify.com
SHOPIFY_STOREFRONT_TOKEN=your_storefront_token
SHOPIFY_ADMIN_TOKEN=shpat_your_admin_token

# Server
BASE_URL=http://43.154.181.44
DOMAIN_NAME=43.154.181.44
DATABASE_PATH=/opt/three-layer-stations/orders.db

# Admin
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your_password

# Price Match (Cover Product)
UNIT_PRICE=100
UNIT_VARIANT_GID=gid://shopify/ProductVariant/45069946945672

# Feishu
FEISHU_APP_ID=cli_xxxxxxxxxxxx
FEISHU_APP_SECRET=your_app_secret
FEISHU_BITABLE_APP_TOKEN=your_bitable_token
FEISHU_BITABLE_TABLE_ID=tbl_xxxxxxxx
```

---

## 产品管理

### A站 WooCommerce (产品数据源)
- 地址: `127.0.0.1:8080` (仅内网，SSH隧道访问)
- 管理员: admin/admin123
- 用途: 管理商品信息，通过 `sync_products.py` 同步到落地页

### Shopify Cover Product
- 店铺: `147xvt-jc.myshopify.com`
- 产品: Luxury Gift Collection
- 变体: 20个 ($100-$2000 区间)
- 策略: 根据订单金额匹配合适的变体，无需折扣码

---

## 常见问题

### Q: 如何切换过审页面到落地页？
在A站服务器上:
```bash
# 过审 → 落地页 (秒切)
# 已配置好 review.html 和 landing.html
# 反爬检测通过 → landing.html，否则 → review.html
# 或者手动改nginx:
sudo sed -i 's/index review.html/index landing.html/' /etc/nginx/sites-available/landing
sudo systemctl reload nginx
```

### Q: 如何添加新产品？
1. 登录 A站 WooCommerce (SSH隧道:8080)
2. 添加产品 + 变体
3. SSH A站执行同步: `cd /home/ubuntu/landing-backend && python sync_products.py`
4. 前端 `data/products.json` 自动更新

### Q: 防爬虫机制有哪些？
1. **字体反爬**: 自定义WOFF2字体，文字在HTML中是编码状态，浏览器渲染才显示
2. **UA检测**: Nginx层拦截常见爬虫UA，返回review.html
3. **JS指纹**: 可在 `app.js` 中加入屏幕宽高/WebGL检测
4. **IP限制**: Nginx + Cloudflare Challenge (可选)

### Q: 如何对接WhatsApp销售？
飞书Bitable作为中转：WA销售创建订单 → 飞书记录 → 运营审核 → 生成结算链接 → 发给客户

---

## License
MIT
