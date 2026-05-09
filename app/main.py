import os
import json
import re
import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Optional

import httpx
from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv

from app.models import CheckoutResponse
from app.wc_api import wc_create_order, wc_get_order, wc_update_order, wc_list_orders
from app.shopify import (
    COVER_PRODUCTS,
    get_tier_for_price,
    create_checkout_cart,
    initialize_cover_products,
    verify_webhook_hmac,
    get_variant_for_checkout,
    select_variant_for_price,
    try_refresh_luxury_variants,
    calculate_price_match,
    get_unit_variant_gid,
)
from app.shopify_admin import create_one_time_discount
from app.sync_feishu import sync_order_created, sync_order_updated

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
DOMAIN_NAME = os.getenv("DOMAIN_NAME", "localhost")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: initialize cover products."""
    logger.info("Starting Three-Layer Station System...")
    try:
        await initialize_cover_products()
    except Exception as e:
        logger.error("Failed to initialize cover products: %s", e)
        logger.warning("System will start but checkout may fail until products are available")

    try:
        async with httpx.AsyncClient(timeout=3) as client:
            await client.get(
                "http://127.0.0.1:8080/wp-content/orders-api.php?action=list&limit=1",
                headers={"X-API-Key": "apk_b9a7c3d1e5f8024679b1a3c5d7e9f0b1"},
            )
    except Exception as e:
        logger.warning("WooCommerce health check failed: %s", e)

    if not os.getenv("SHOPIFY_STOREFRONT_TOKEN", ""):
        logger.warning("SHOPIFY_STOREFRONT_TOKEN env is empty")
    if not os.getenv("SHOPIFY_ADMIN_TOKEN", "").startswith("shpat_"):
        logger.warning("SHOPIFY_ADMIN_TOKEN does not start with 'shpat_'")

    yield
    logger.info("Shutting down Three-Layer Station System...")


app = FastAPI(
    title="Three-Layer Station System (三层站群支付系统)",
    version="2.0.0",
    lifespan=lifespan,
)


@app.middleware("http")
async def api_key_auth_middleware(request: Request, call_next):
    if request.url.path == "/health":
        return await call_next(request)

    expected = os.getenv("API_AUTH_KEY", "apk_b9a7c3d1e5f80")
    provided = request.headers.get("X-Api-Key", "")
    if provided != expected:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=401, content={"detail": "Invalid or missing API key"})

    return await call_next(request)


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------
class CreateOrderRequest(BaseModel):
    session_id: str
    total_price: float
    phone: str
    items: list
    customer_name: Optional[str] = ""


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------
@app.get("/health")
async def health():
    """Health check endpoint."""
    wc_ok = False
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            resp = await client.get(
                "http://127.0.0.1:8080/wp-content/orders-api.php?action=list&limit=1",
                headers={"X-API-Key": "apk_b9a7c3d1e5f8024679b1a3c5d7e9f0b1"},
            )
            wc_ok = resp.status_code == 200
    except Exception as e:
        logger.warning("WooCommerce health check failed: %s", e)
        wc_ok = False

    storefront_ok = bool(os.getenv("SHOPIFY_STOREFRONT_TOKEN", ""))
    admin_ok = os.getenv("SHOPIFY_ADMIN_TOKEN", "").startswith("shpat_")
    shopify_token_ok = storefront_ok and admin_ok

    return {
        "status": "ok",
        "system": "three-layer-stations",
        "version": "2.0.0",
        "wc": wc_ok,
        "shopify_token": shopify_token_ok,
    }


# ---------------------------------------------------------------------------
# Order creation API (delegates persistence to WooCommerce via wc_api)
# ---------------------------------------------------------------------------
async def _create_order_and_variant(req: CreateOrderRequest) -> dict:
    """Shared logic: create a WC order keyed by session_id and resolve a Shopify variant."""
    try:
        wc_result = await wc_create_order(
            req.session_id,
            req.customer_name or "",
            req.phone,
            req.items,
            req.total_price,
        )
    except Exception as e:
        logger.error("Failed to create WC order for session %s: %s", req.session_id, e)
        raise HTTPException(status_code=502, detail=f"Failed to create order: {str(e)}")

    # Sync to Feishu Bitable and store record_id
    feishu_rec_id = await sync_order_created(
        session_id=req.session_id,
        phone=req.phone,
        total_price=req.total_price,
        items=req.items,
        status="pending",
        order_id=wc_result.get("order_id"),
    )
    if feishu_rec_id:
        await wc_update_order(req.session_id, feishu_record_id=feishu_rec_id)

    variant_info = await get_variant_for_checkout(req.total_price)
    match = calculate_price_match(req.total_price)

    logger.info(
        "Order created: session=%s | Price: $%.2f | Variant: %s",
        req.session_id,
        req.total_price,
        variant_info.get("variant_title", "unknown"),
    )

    return {
        "session_id": req.session_id,
        "order_id": wc_result.get("order_id"),
        "status": wc_result.get("status"),
        "checkout_url": wc_result.get("checkout_url", ""),
        "variant_used": variant_info.get("variant_title", ""),
        "variant_price": variant_info.get("price", req.total_price),
        "variant_gid": variant_info.get("variant_gid", ""),
        "tier_name": variant_info.get("tier_name", ""),
        "unit_quantity": match["qty"],
        "unit_price": match["unit_price"],
        "discount_amount": match["discount"],
        "feishu_synced": bool(feishu_rec_id),
    }


@app.post("/api/orders")
async def create_order(req: CreateOrderRequest):
    """Create a new order via WooCommerce and return Shopify variant info."""
    return await _create_order_and_variant(req)


@app.post("/api/create_checkout")
async def create_checkout_from_a_station(req: CreateOrderRequest):
    """Entry point used by A站: create order AND Shopify checkout in one call."""
    order_data = await _create_order_and_variant(req)

    try:
        checkout_info = await _create_checkout_for_order(req.session_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Order created but checkout creation failed for session %s: %s",
            req.session_id, e,
        )
        raise HTTPException(
            status_code=502,
            detail=f"Order created but failed to create Shopify checkout: {str(e)}",
        )

    return {
        **order_data,
        "checkout_url": checkout_info.checkout_url,
        "discount_code": checkout_info.discount_code,
        "unit_quantity": checkout_info.unit_quantity,
        "unit_price": checkout_info.unit_price,
        "discount_amount": checkout_info.discount_amount,
    }


# ---------------------------------------------------------------------------
# Checkout creation
# ---------------------------------------------------------------------------
async def _create_checkout_for_order(session_id: str) -> CheckoutResponse:
    """Shared logic: create a Shopify checkout for an existing WC order.

    Performs discount-code creation, Shopify cart creation, persists the
    checkout URL on the order, and syncs the update to Feishu. If a checkout
    already exists for this session, the existing URL is returned.
    """
    order = await wc_get_order(session_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if order.get("status") == "checkout_created" and order.get("checkout_url"):
        logger.info("Checkout already exists for session %s, returning existing URL", session_id)
        return CheckoutResponse(
            checkout_url=order["checkout_url"],
            discount_code=order.get("discount_code", "") or "",
            unit_quantity=order.get("unit_quantity", 0) or 0,
            unit_price=order.get("unit_price", 99.0) or 99.0,
            discount_amount=order.get("discount_amount", 0.0) or 0.0,
        )

    price = float(order.get("total_price") or order.get("price") or 0.0)
    match = calculate_price_match(price)
    qty = int(order.get("unit_quantity") or match["qty"] or 1)
    unit_price = float(order.get("unit_price") or match["unit_price"] or 99.0)
    discount_amount = float(order.get("discount_amount") or match["discount"] or 0.0)

    code = ""
    if discount_amount > 0:
        try:
            code = f"ORDER-{session_id}"
            await create_one_time_discount(discount_amount, code)
            logger.info(
                "Created one-time discount for session %s: code=%s amount=$%.2f",
                session_id, code, discount_amount,
            )
        except Exception as de:
            logger.warning(
                "Discount creation failed for session %s — proceeding without discount. "
                "Customer will pay $%.2f instead of $%.2f. Error: %s",
                session_id,
                qty * unit_price,
                price,
                de,
            )
            code = ""

    variant_gid = get_unit_variant_gid()

    cart = await create_checkout_cart(
        variant_gid,
        session_id,
        quantity=qty,
        discount_code=code or None,
    )
    checkout_url = cart.get("checkoutUrl")
    cart_id = cart.get("id")

    if not checkout_url:
        raise Exception("No checkout URL returned from Shopify")

    await wc_update_order(
        session_id,
        status="checkout_created",
        checkout_url=checkout_url,
        cart_id=cart_id,
    )

    await sync_order_updated(
        session_id=session_id,
        status="checkout_created",
        checkout_url=checkout_url,
        feishu_record_id=order.get("feishu_record_id"),
    )

    logger.info(
        "Checkout created for session %s: %s (qty=%d @ $%.2f, discount=%s/$%.2f)",
        session_id,
        checkout_url,
        qty,
        unit_price,
        code or "<none>",
        discount_amount,
    )
    return CheckoutResponse(
        checkout_url=checkout_url,
        discount_code=code,
        unit_quantity=qty,
        unit_price=unit_price,
        discount_amount=discount_amount,
    )


@app.post("/api/checkout/{session_id}", response_model=CheckoutResponse)
async def create_checkout(session_id: str):
    """Create a Shopify checkout for the given order using the unit-price + discount-code flow."""
    try:
        return await _create_checkout_for_order(session_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to create checkout for session %s: %s", session_id, e)
        raise HTTPException(
            status_code=502,
            detail=f"Failed to create Shopify checkout: {str(e)}",
        )


# ---------------------------------------------------------------------------
# Webhook handler
# ---------------------------------------------------------------------------
@app.post("/api/webhook/shopify")
async def shopify_webhook(request: Request):
    """Receive Shopify order/webhook notifications."""
    body = await request.body()
    signature = request.headers.get("X-Shopify-Hmac-Sha256", "")
    topic = request.headers.get("X-Shopify-Topic", "")

    if not verify_webhook_hmac(body, signature):
        raise HTTPException(status_code=401, detail="Invalid HMAC signature")

    logger.info("Received Shopify webhook: topic=%s", topic)

    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    if topic == "orders/create":
        shopify_order_id = str(data.get("id", ""))
        cart_token = data.get("cart_token", "")
        note = data.get("note", "")
        total_price = data.get("total_price", "")
        order_number = data.get("order_number", "")

        logger.info(
            "Shopify order #%s created: id=%s, cart_token=%s, total=%s",
            order_number,
            shopify_order_id,
            cart_token,
            total_price,
        )

        session_id = None
        if note:
            match = re.search(r"Order Reference:\s*(\w+)", note)
            if match:
                session_id = match.group(1)

        if session_id:
            order = await wc_get_order(session_id)
            if order:
                await wc_update_order(
                    session_id,
                    status="paid",
                    shopify_order_id=shopify_order_id,
                )
                # Sync paid status to Feishu
                await sync_order_updated(
                    session_id=session_id,
                    status="paid",
                    shopify_order_id=shopify_order_id,
                    feishu_record_id=order.get("feishu_record_id"),
                )
                logger.info(
                    "Order %s updated to 'paid' (Shopify Order #%s)",
                    session_id, order_number,
                )
            else:
                logger.warning("Order %s not found in WooCommerce", session_id)
        else:
            logger.warning("Could not extract session_id from webhook note: %s", note)

    elif topic == "orders/fulfilled":
        shopify_order_id = str(data.get("id", ""))
        orders = await wc_list_orders(limit=100)
        for o in orders:
            if str(o.get("shopify_order_id", "")) == shopify_order_id:
                target_session = o.get("session_id") or o.get("id")
                if target_session:
                    await wc_update_order(target_session, status="fulfilled")
                    # Sync fulfilled status to Feishu
                    await sync_order_updated(
                        session_id=target_session,
                        status="fulfilled",
                        shopify_order_id=shopify_order_id,
                        feishu_record_id=o.get("feishu_record_id"),
                    )
                    logger.info("Order %s updated to 'fulfilled'", target_session)
                break
    else:
        logger.info("Unhandled webhook topic: %s", topic)

    return {"status": "received"}


# ---------------------------------------------------------------------------
# Order API endpoints
# ---------------------------------------------------------------------------
@app.get("/api/orders")
async def get_order_api(session_id: str):
    """Get order details by session_id."""
    order = await wc_get_order(session_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order