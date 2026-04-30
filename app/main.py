import os
import json
import re
import secrets
import string
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException, Response
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

from app.models import OrderCreateRequest
from app.database import init_db, insert_order, get_order, update_order, list_orders, search_orders
from app.shopify import (
    COVER_PRODUCTS,
    get_tier_for_price,
    create_checkout_cart,
    initialize_cover_products,
    verify_webhook_hmac,
    get_variant_for_checkout,
    select_variant_for_price,
    try_refresh_luxury_variants,
)

# Load environment variables
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
DOMAIN_NAME = os.getenv("DOMAIN_NAME", "localhost")

# Admin credentials (simple hardcoded for now — change in production)
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: initialize DB and cover products."""
    logger.info("Starting Three-Layer Station System...")
    init_db()
    try:
        await initialize_cover_products()
    except Exception as e:
        logger.error("Failed to initialize cover products: %s", e)
        logger.warning("System will start but checkout may fail until products are available")
    yield
    logger.info("Shutting down Three-Layer Station System...")


app = FastAPI(
    title="Three-Layer Station System (三层站群支付系统)",
    version="2.0.0",
    lifespan=lifespan,
)

# Templates
template_dir = os.path.join(os.path.dirname(__file__), "templates")
templates = Jinja2Templates(directory=template_dir)


def generate_order_id(length: int = 8) -> str:
    """Generate a random alphanumeric order ID."""
    chars = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(chars) for _ in range(length))


def verify_admin(request: Request) -> bool:
    """Simple Basic Auth verification for admin routes."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Basic "):
        return False
    import base64
    try:
        decoded = base64.b64decode(auth[6:]).decode("utf-8")
        username, password = decoded.split(":", 1)
        return username == ADMIN_USERNAME and password == ADMIN_PASSWORD
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------
@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "ok",
        "system": "three-layer-stations",
        "version": "2.0.0",
    }


# ---------------------------------------------------------------------------
# Order creation API (with real product mapping)
# ---------------------------------------------------------------------------
@app.post("/api/orders")
async def create_order(req: OrderCreateRequest):
    """Create a new order and return the landing page URL."""
    order_id = generate_order_id()

    # Select the appropriate Shopify variant for this price
    variant_info = await get_variant_for_checkout(req.price)

    order_data = {
        "id": order_id,
        "product_name": req.product_name,
        "product_spec": req.product_spec or "",
        "product_image_url": req.product_image_url or "",
        "price": req.price,
        "customer_name": req.customer_name or "",
        "customer_phone": req.customer_phone or "",
        "currency": "USD",
        "status": "pending",
        # Real product mapping
        "real_product_name": req.product_name,
        "real_product_spec": req.product_spec or "",
        "real_product_image": req.product_image_url or "",
        # Shopify variant info
        "shopify_variant_id": variant_info.get("variant_gid", ""),
        "shopify_variant_price": variant_info.get("price", req.price),
        "cover_product_id": variant_info.get("tier_name", ""),
    }

    try:
        inserted = insert_order(order_data)
        logger.info(
            "Order created: %s | Real product: %s | Price: $%.2f | Variant: %s",
            order_id,
            req.product_name,
            req.price,
            variant_info.get("variant_title", "unknown"),
        )
        return {
            "order_id": order_id,
            "page_url": f"{BASE_URL}/order/{order_id}",
            "variant_used": variant_info.get("variant_title", ""),
            "variant_price": variant_info.get("price", req.price),
        }
    except Exception as e:
        logger.error("Failed to create order: %s", e)
        raise HTTPException(status_code=500, detail=f"Failed to create order: {str(e)}")


# ---------------------------------------------------------------------------
# Order page (landing page)
# ---------------------------------------------------------------------------
@app.get("/order/{order_id}", response_class=HTMLResponse)
async def render_order_page(request: Request, order_id: str):
    """Render the mobile-first landing page for an order."""
    order = get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    return templates.TemplateResponse(
        "order.html",
        {
            "request": request,
            "order": order,
            "order_id": order_id,
            "domain_name": DOMAIN_NAME,
        },
    )


# ---------------------------------------------------------------------------
# Checkout creation
# ---------------------------------------------------------------------------
@app.post("/api/checkout/{order_id}")
async def create_checkout(order_id: str):
    """Create a Shopify checkout for the given order."""
    order = get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    # Don't create a new checkout if one already exists
    if order["status"] == "checkout_created" and order.get("checkout_url"):
        logger.info("Checkout already exists for order %s, returning existing URL", order_id)
        return {"checkout_url": order["checkout_url"]}

    price = order["price"]

    # Use the variant already stored in the order, or select a new one
    variant_gid = order.get("shopify_variant_id", "")
    if not variant_gid:
        variant_info = await get_variant_for_checkout(price)
        variant_gid = variant_info.get("variant_gid", "")
        variant_price = variant_info.get("price", price)
        variant_title = variant_info.get("variant_title", "")
        tier_name = variant_info.get("tier_name", "")
    else:
        variant_price = order.get("shopify_variant_price", price)
        variant_title = order.get("cover_product_id", "")
        tier_name = order.get("cover_product_id", "")

    if not variant_gid:
        # Last resort: fallback to legacy
        tier_name, tier_info = get_tier_for_price(price)
        variant_gid = tier_info.get("variant_gid")
        variant_price = tier_info.get("price", price)
        variant_title = tier_info.get("name", "")

    if not variant_gid:
        raise HTTPException(
            status_code=500,
            detail="No cover product variant configured. Please initialize products first.",
        )

    try:
        cart = await create_checkout_cart(variant_gid, order_id)
        checkout_url = cart.get("checkoutUrl")
        cart_id = cart.get("id")

        if not checkout_url:
            raise Exception("No checkout URL returned from Shopify")

        # Update order in database
        update_kwargs = {
            "status": "checkout_created",
            "checkout_url": checkout_url,
            "shopify_cart_id": cart_id,
            "cover_product_id": tier_name,
            "shopify_variant_id": variant_gid,
            "shopify_variant_price": variant_price,
        }
        update_order(order_id, **update_kwargs)

        logger.info(
            "Checkout created for order %s: %s (variant: %s @ $%.2f)",
            order_id,
            checkout_url,
            variant_title,
            variant_price,
        )
        return {"checkout_url": checkout_url}

    except Exception as e:
        logger.error("Failed to create checkout for order %s: %s", order_id, e)
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

    # Verify HMAC signature
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

        # Extract our order reference from the cart note
        order_id = None
        if note:
            match = re.search(r"Order Reference:\s*(\w+)", note)
            if match:
                order_id = match.group(1)

        if order_id:
            order = get_order(order_id)
            if order:
                update_order(
                    order_id,
                    status="paid",
                    shopify_order_id=shopify_order_id,
                )
                logger.info("Order %s updated to 'paid' (Shopify Order #%s)", order_id, order_number)
            else:
                logger.warning("Order %s not found in database", order_id)
        else:
            logger.warning("Could not extract order_id from webhook note: %s", note)

    elif topic == "orders/fulfilled":
        shopify_order_id = str(data.get("id", ""))
        # Find order by shopify_order_id and mark as fulfilled
        orders = list_orders(limit=100)
        for o in orders:
            if o.get("shopify_order_id") == shopify_order_id:
                update_order(o["id"], status="fulfilled")
                logger.info("Order %s updated to 'fulfilled'", o["id"])
                break
    else:
        logger.info("Unhandled webhook topic: %s", topic)

    return {"status": "received"}


# ---------------------------------------------------------------------------
# Order API endpoints
# ---------------------------------------------------------------------------
@app.get("/api/orders/{order_id}")
async def get_order_api(order_id: str):
    """Get order details via API."""
    order = get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@app.get("/api/orders")
async def list_orders_api(limit: int = 50, offset: int = 0, search: str = ""):
    """List all orders with optional search."""
    if search:
        orders = search_orders(search, limit=limit)
    else:
        orders = list_orders(limit=limit, offset=offset)
    return {"orders": orders, "count": len(orders)}


# ---------------------------------------------------------------------------
# Admin Dashboard Routes
# ---------------------------------------------------------------------------
@app.get("/admin/login", response_class=HTMLResponse)
async def admin_login_page(request: Request):
    """Render admin login page."""
    return templates.TemplateResponse("admin_login.html", {"request": request})


@app.post("/admin/login")
async def admin_login(request: Request):
    """Verify admin credentials and set cookie."""
    body = await request.json()
    username = body.get("username", "")
    password = body.get("password", "")
    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        import base64
        token = base64.b64encode(f"{username}:{password}".encode()).decode()
        return {"success": True, "token": token}
    raise HTTPException(status_code=401, detail="Invalid credentials")


@app.get("/admin/orders", response_class=HTMLResponse)
async def admin_orders_page(request: Request):
    """Render the admin order management dashboard."""
    return templates.TemplateResponse(
        "admin_orders.html",
        {
            "request": request,
            "domain_name": DOMAIN_NAME,
        },
    )


@app.get("/api/admin/orders")
async def admin_list_orders(request: Request, limit: int = 100, offset: int = 0, search: str = ""):
    """API endpoint for admin dashboard to fetch orders."""
    if not verify_admin(request):
        raise HTTPException(status_code=401, detail="Unauthorized")

    if search:
        orders = search_orders(search, limit=limit)
    else:
        orders = list_orders(limit=limit, offset=offset)

    # Convert for JSON serialization
    result = []
    for order in orders:
        result.append({
            "id": order.get("id", ""),
            "real_product_name": order.get("real_product_name", order.get("product_name", "")),
            "real_product_spec": order.get("real_product_spec", ""),
            "real_product_image": order.get("real_product_image", order.get("product_image_url", "")),
            "product_name": order.get("product_name", ""),
            "price": order.get("price", 0),
            "currency": order.get("currency", "USD"),
            "customer_name": order.get("customer_name", ""),
            "customer_phone": order.get("customer_phone", ""),
            "status": order.get("status", "pending"),
            "checkout_url": order.get("checkout_url", ""),
            "shopify_order_id": order.get("shopify_order_id", ""),
            "shopify_variant_id": order.get("shopify_variant_id", ""),
            "shopify_variant_price": order.get("shopify_variant_price", 0),
            "shopify_cart_id": order.get("shopify_cart_id", ""),
            "cover_product_id": order.get("cover_product_id", ""),
            "created_at": order.get("created_at", ""),
            "updated_at": order.get("updated_at", ""),
        })

    return {"orders": result, "count": len(result)}


@app.post("/api/admin/orders/{order_id}/status")
async def admin_update_order_status(request: Request, order_id: str):
    """Update order status from admin dashboard."""
    if not verify_admin(request):
        raise HTTPException(status_code=401, detail="Unauthorized")

    body = await request.json()
    new_status = body.get("status", "")
    valid_statuses = ["pending", "checkout_created", "paid", "fulfilled", "cancelled"]

    if new_status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}")

    order = get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    update_order(order_id, status=new_status)
    logger.info("Admin updated order %s status to '%s'", order_id, new_status)
    return {"success": True, "order_id": order_id, "status": new_status}


@app.post("/api/admin/orders/{order_id}/refresh-variant")
async def admin_refresh_variant(request: Request, order_id: str):
    """Manually trigger variant refresh for an order."""
    if not verify_admin(request):
        raise HTTPException(status_code=401, detail="Unauthorized")

    order = get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    price = order.get("price", 0)
    variant_info = await get_variant_for_checkout(price)

    update_order(
        order_id,
        shopify_variant_id=variant_info.get("variant_gid", ""),
        shopify_variant_price=variant_info.get("price", price),
        cover_product_id=variant_info.get("tier_name", ""),
    )

    return {
        "success": True,
        "order_id": order_id,
        "variant_gid": variant_info.get("variant_gid", ""),
        "variant_title": variant_info.get("variant_title", ""),
        "variant_price": variant_info.get("price", price),
    }


@app.post("/api/admin/refresh-shopify-products")
async def admin_refresh_products(request: Request):
    """Force refresh the luxury variants from Shopify."""
    if not verify_admin(request):
        raise HTTPException(status_code=401, detail="Unauthorized")

    success = await try_refresh_luxury_variants()
    if success:
        return {"success": True, "message": "Luxury variants refreshed successfully"}
    else:
        return {"success": False, "message": "Luxury Gift Collection not found in store"}
