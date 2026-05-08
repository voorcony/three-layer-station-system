#!/usr/bin/env python3
"""
checkout_api.py — Shopify Checkout API
根据购物车总价匹配 Cover Product 变体，创建 Shopify Checkout URL

启动: uvicorn checkout_api:app --host 127.0.0.1 --port 8099
"""
import json
import os
import re
import uuid
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
import httpx

app = FastAPI(title="Landing Checkout API", version="1.0.0")

# ===== 配置（环境变量，带默认值） =====
SHOPIFY_STORE = os.getenv("SHOPIFY_STORE", "147xvt-jc.myshopify.com")
SHOPIFY_STOREFRONT_TOKEN = os.getenv("SHOPIFY_STOREFRONT_TOKEN", "48382a763d8f47c5bf40b7983eeb2d73")
SHOPIFY_CLIENT_SECRET = os.getenv("SHOPIFY_CLIENT_SECRET", "")

# Cover Product 变体映射: 价格阈值(≤) → 变体GID
# 在 Shopify 后台创建 Cover Product 的多个变体后填入
DEFAULT_TIERS = {
    100:  "gid://shopify/ProductVariant/COVER_1",
    200:  "gid://shopify/ProductVariant/COVER_2",
    300:  "gid://shopify/ProductVariant/COVER_3",
    500:  "gid://shopify/ProductVariant/COVER_4",
    1000: "gid://shopify/ProductVariant/COVER_5",
    2000: "gid://shopify/ProductVariant/COVER_6",
}

# 尝试从环境变量读取 tiers JSON
_tiers_env = os.getenv("COVER_TIERS")
if _tiers_env:
    try:
        COVER_TIERS = {int(k): v for k, v in json.loads(_tiers_env).items()}
    except (ValueError, json.JSONDecodeError):
        COVER_TIERS = DEFAULT_TIERS
else:
    COVER_TIERS = DEFAULT_TIERS

# ===== 数据模型 =====

class CheckoutRequest(BaseModel):
    session_id: str
    total_price: float
    phone: str
    items: list

class OrderRecord(BaseModel):
    session_id: str
    phone: str
    items: list
    total_price: float
    checkout_url: str = ""
    cart_id: str = ""
    shopify_order_id: str = ""
    status: str = "pending"
    created_at: str = ""

# 内存存储（生产环境改用 Redis/SQLite）
orders: dict[str, OrderRecord] = {}

# ===== 工具函数 =====

def get_tier_for_price(price: float) -> tuple[int, str]:
    """根据价格匹配最合适的 cover product 变体"""
    sorted_thresholds = sorted(COVER_TIERS.keys())
    matched = sorted_thresholds[0]
    for t in sorted_thresholds:
        if price <= t:
            return t, COVER_TIERS[t]
        matched = t
    return matched, COVER_TIERS[matched]

async def create_shopify_cart(variant_gid: str, note: str) -> tuple[Optional[str], Optional[str]]:
    """通过 Shopify Storefront API 创建 cart，返回 (cart_id, checkout_url)"""
    if not SHOPIFY_STOREFRONT_TOKEN:
        return None, None

    query = """
    mutation cartCreate($input: CartInput!) {
        cartCreate(input: $input) {
            cart { id checkoutUrl totalQuantity }
            userErrors { field message }
        }
    }
    """
    variables = {
        "input": {
            "lines": [{"merchandiseId": variant_gid, "quantity": 1}],
            "note": note[:250],  # Shopify note limit
        }
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"https://{SHOPIFY_STORE}/api/2024-10/graphql.json",
                json={"query": query, "variables": variables},
                headers={"X-Shopify-Storefront-Access-Token": SHOPIFY_STOREFRONT_TOKEN},
            )
            data = resp.json()
            cart = data.get("data", {}).get("cartCreate", {}).get("cart")
            if cart:
                return cart.get("id"), cart.get("checkoutUrl")
            errors = data.get("data", {}).get("cartCreate", {}).get("userErrors", [])
            if errors:
                print(f"Shopify cartCreate errors: {errors}", file=__import__('sys').stderr)
    except Exception as e:
        print(f"Shopify API error: {e}", file=__import__('sys').stderr)

    return None, None

# ===== API 路由 =====

@app.post("/api/create_checkout")
async def create_checkout(req: CheckoutRequest):
    """创建 Shopify checkout 并返回结算链接"""
    # 1. 匹配 cover product 变体
    tier_price, variant_gid = get_tier_for_price(req.total_price)
    note = f"Session: {req.session_id} | Phone: {req.phone}"

    # 2. 创建订单记录
    order = OrderRecord(
        session_id=req.session_id,
        phone=req.phone,
        items=req.items,
        total_price=req.total_price,
        created_at=datetime.now().isoformat(),
    )

    # 3. 尝试通过 Storefront API 创建 cart
    cart_id, checkout_url = await create_shopify_cart(variant_gid, note)

    # 4. 降级：直接链接到店铺首页，订单数据已保存
    if not checkout_url:
        checkout_url = (
            f"https://{SHOPIFY_STORE}/?session_id={req.session_id}"
        )

    order.checkout_url = checkout_url
    order.cart_id = cart_id or ""
    order.status = "checkout_created"
    orders[req.session_id] = order

    print(f"[checkout] {req.session_id} → {checkout_url[:80]}...", file=__import__('sys').stderr)

    return {
        "checkout_url": checkout_url,
        "session_id": req.session_id,
        "cart_id": cart_id,
        "tier_price": tier_price,
    }

@app.get("/api/order/{session_id}")
async def get_order(session_id: str):
    """查询订单状态"""
    order = orders.get(session_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order.dict()

@app.post("/api/webhook/shopify")
async def shopify_webhook(request: Request):
    """接收 Shopify 订单创建 webhook"""
    body = await request.body()
    data = json.loads(body)
    topic = request.headers.get("X-Shopify-Topic", "")

    if topic == "orders/create":
        order_id = data.get("id", "")
        note = data.get("note", "")
        attributes = {a["name"]: a["value"] for a in data.get("note_attributes", [])}

        # 从 note 或 attributes 提取 session_id
        session_id = attributes.get("_session_id", "")
        if not session_id and note:
            match = re.search(r"Session:\s*(\S+)", note)
            if match:
                session_id = match.group(1)

        if session_id and session_id in orders:
            orders[session_id].shopify_order_id = str(order_id)
            orders[session_id].status = "paid"
            print(f"[webhook] Order {order_id} → Session {session_id} → PAID ✅",
                  file=__import__('sys').stderr)
        else:
            print(f"[webhook] Order {order_id} — session_id '{session_id}' not found",
                  file=__import__('sys').stderr)

    return {"status": "ok"}

@app.get("/health")
async def health():
    return {"status": "ok", "orders_count": len(orders), "timestamp": datetime.now().isoformat()}
