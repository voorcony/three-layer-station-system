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
        action_urls={
            "cancel": f"{BASE_URL}/api/order/{req.session_id}/cancel",
            "refresh": f"{BASE_URL}/api/order/{req.session_id}/refresh",
            "view": f"{BASE_URL}/api/orders?session_id={req.session_id}",
        },
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
        "action_urls": {
            "cancel": f"{BASE_URL}/api/order/{req.session_id}/cancel",
            "refresh": f"{BASE_URL}/api/order/{req.session_id}/refresh",
            "view": f"{BASE_URL}/api/orders?session_id={req.session_id}",
        },
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


_FALLBACK_PRODUCTS = [
    {
        "id": 1,
        "name": "奢华礼品套装",
        "type": "variable",
        "description": "精选高端礼品套装",
        "images": [],
        "categories": ["礼品套装"],
        "attributes": [
            {"name": "档次", "options": ["标准", "豪华", "尊享"], "variation": True},
            {"name": "包装", "options": ["简约", "礼盒", "精装", "限定版"], "variation": True},
        ],
        "variants": [
            {"id": 101, "sku": "SET-A", "price": 99, "stock_status": "instock",
             "attributes": {"档次": "标准", "包装": "简约"}},
            {"id": 102, "sku": "SET-B", "price": 149, "stock_status": "instock",
             "attributes": {"档次": "标准", "包装": "礼盒"}},
            {"id": 103, "sku": "SET-C", "price": 199, "stock_status": "instock",
             "attributes": {"档次": "豪华", "包装": "礼盒"}},
            {"id": 104, "sku": "SET-D", "price": 299, "stock_status": "instock",
             "attributes": {"档次": "豪华", "包装": "精装"}},
            {"id": 105, "sku": "SET-E", "price": 499, "stock_status": "instock",
             "attributes": {"档次": "尊享", "包装": "精装"}},
            {"id": 106, "sku": "SET-F", "price": 999, "stock_status": "instock",
             "attributes": {"档次": "尊享", "包装": "限定版"}},
        ],
    },
    {
        "id": 2,
        "name": "精美手表",
        "type": "simple",
        "description": "经典设计，精工品质",
        "images": [],
        "categories": ["手表"],
        "price": 299,
        "stock_status": "instock",
        "sku": "WATCH-001",
    },
]

_WP_CONTAINER = os.getenv("WP_CONTAINER", "b-woocommerce-wp")


async def _run_wp_cli(*wp_args: str, timeout: float = 15.0) -> Optional[list]:
    """Run a wp-cli command in the WooCommerce docker container and parse JSON output.

    Returns the parsed JSON list on success, or None on failure (non-zero exit,
    timeout, missing docker, or invalid JSON).
    """
    cmd = ["docker", "exec", _WP_CONTAINER, "wp", *wp_args, "--allow-root"]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except (FileNotFoundError, OSError) as e:
        logger.warning("wp-cli exec failed (docker missing?): %s", e)
        return None

    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        logger.warning("wp-cli command timed out: %s", " ".join(cmd))
        try:
            proc.kill()
        except ProcessLookupError:
            pass
        return None

    if proc.returncode != 0:
        logger.warning(
            "wp-cli command failed (rc=%s): %s | stderr=%s",
            proc.returncode, " ".join(cmd), stderr.decode("utf-8", "replace").strip(),
        )
        return None

    try:
        data = json.loads(stdout.decode("utf-8", "replace") or "[]")
    except json.JSONDecodeError as e:
        logger.warning("wp-cli returned non-JSON output: %s", e)
        return None

    if not isinstance(data, list):
        logger.warning("wp-cli JSON was not a list: %r", type(data).__name__)
        return None
    return data


async def _fetch_products_via_wp_cli() -> Optional[list]:
    """Fetch products (and variants) from WooCommerce via wp-cli.

    Returns a list shaped like the static fallback catalog, or None on error.
    """
    posts = await _run_wp_cli(
        "post", "list",
        "--post_type=product",
        "--format=json",
    )
    if posts is None:
        return None

    products: list = []
    for post in posts:
        try:
            pid = int(post.get("ID"))
        except (TypeError, ValueError):
            continue
        name = post.get("post_title") or ""

        variations = await _run_wp_cli(
            "post", "list",
            "--post_type=product_variation",
            "--format=json",
            f"--post_parent={pid}",
        )

        if variations:
            variants = []
            for v in variations:
                try:
                    vid = int(v.get("ID"))
                except (TypeError, ValueError):
                    continue
                variants.append({
                    "id": vid,
                    "sku": v.get("post_name") or f"VAR-{vid}",
                    "price": 0,
                    "stock_status": "instock",
                    "attributes": {},
                })
            products.append({
                "id": pid,
                "name": name,
                "type": "variable",
                "description": post.get("post_excerpt") or "",
                "images": [],
                "categories": [],
                "attributes": [],
                "variants": variants,
            })
        else:
            products.append({
                "id": pid,
                "name": name,
                "type": "simple",
                "description": post.get("post_excerpt") or "",
                "images": [],
                "categories": [],
                "price": 0,
                "stock_status": "instock",
                "sku": post.get("post_name") or f"PROD-{pid}",
            })

    return products


@app.get("/api/products")
async def list_products():
    """Return product catalog for A站 sync_products.py.

    Pulls live data from WooCommerce via products-api.php (PHP + WC API).
    Falls back to a static demo catalog if the PHP endpoint fails.
    """
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "http://127.0.0.1:8080/wp-content/products-api.php?action=list&category=landing",
                headers={"X-API-Key": "apk_b9a7c3d1e5f8024679b1a3c5d7e9f0b1"},
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("success") and data.get("products"):
                    return {"success": True, "products": data["products"], "source": "woocommerce"}
    except Exception as e:
        logger.warning("products-api.php failed: %s", e)

    logger.info("products-api.php unavailable, returning fallback catalog")
    return {"success": True, "products": _FALLBACK_PRODUCTS, "source": "fallback"}


@app.api_route("/api/order/{session_id}/cancel", methods=["GET", "POST"])
async def cancel_order(session_id: str):
    """Cancel an order if it has not yet been paid or fulfilled."""
    order = await wc_get_order(session_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    current_status = order.get("status", "")
    if current_status in ("paid", "fulfilled"):
        logger.warning(
            "Refusing to cancel session %s: order already in status '%s'",
            session_id, current_status,
        )
        raise HTTPException(
            status_code=409,
            detail=f"Cannot cancel order in status '{current_status}'",
        )

    await wc_update_order(session_id, status="cancelled")
    await sync_order_updated(
        session_id=session_id,
        status="cancelled",
        feishu_record_id=order.get("feishu_record_id"),
    )

    logger.info("Order %s cancelled", session_id)
    return {"status": "ok", "order_status": "cancelled"}


@app.api_route("/api/order/{session_id}/refresh", methods=["GET", "POST"])
async def refresh_order_checkout(session_id: str):
    """Regenerate the Shopify checkout URL for a not-yet-paid order."""
    order = await wc_get_order(session_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    current_status = order.get("status", "")
    if current_status in ("paid", "fulfilled"):
        logger.warning(
            "Refusing to refresh session %s: order already in status '%s'",
            session_id, current_status,
        )
        raise HTTPException(
            status_code=409,
            detail=f"Cannot refresh order in status '{current_status}'",
        )

    # Force regeneration by clearing the existing checkout_created status so
    # _create_checkout_for_order doesn't short-circuit and return the old URL.
    if current_status == "checkout_created":
        await wc_update_order(session_id, status="pending")

    try:
        checkout_info = await _create_checkout_for_order(session_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to refresh checkout for session %s: %s", session_id, e)
        raise HTTPException(
            status_code=502,
            detail=f"Failed to refresh Shopify checkout: {str(e)}",
        )

    await wc_update_order(session_id, status="pending")
    await sync_order_updated(
        session_id=session_id,
        status="pending",
        checkout_url=checkout_info.checkout_url,
        feishu_record_id=order.get("feishu_record_id"),
    )

    logger.info("Order %s checkout refreshed: %s", session_id, checkout_info.checkout_url)
    return {"checkout_url": checkout_info.checkout_url, "status": "ok"}