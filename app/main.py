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
from dotenv import load_dotenv

from app.models import OrderCreateRequest
from app.database import init_db, insert_order, get_order, update_order, list_orders
from app.shopify import (
    COVER_PRODUCTS,
    get_tier_for_price,
    create_checkout_cart,
    initialize_cover_products,
    verify_webhook_hmac,
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
    version="1.0.0",
    lifespan=lifespan,
)

# Templates
template_dir = os.path.join(os.path.dirname(__file__), "templates")
templates = Jinja2Templates(directory=template_dir)


def generate_order_id(length: int = 8) -> str:
    """Generate a random alphanumeric order ID."""
    chars = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(chars) for _ in range(length))


# ---------------------------------------------------------------------------
# API Routes
# ---------------------------------------------------------------------------


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "system": "three-layer-stations"}


@app.post("/api/orders")
async def create_order(req: OrderCreateRequest):
    """Create a new order and return the landing page URL."""
    order_id = generate_order_id()
    order_data = {
        "id": order_id,
        "product_name": req.product_name,
        "product_spec": req.product_spec or "",
        "product_image_url": req.product_image_url,
        "price": req.price,
        "customer_name": req.customer_name or "",
        "customer_phone": req.customer_phone or "",
        "currency": "USD",
        "status": "pending",
    }

    try:
        inserted = insert_order(order_data)
        logger.info("Order created: %s", order_id)
        return {
            "order_id": order_id,
            "page_url": f"{BASE_URL}/order/{order_id}",
        }
    except Exception as e:
        logger.error("Failed to create order: %s", e)
        raise HTTPException(status_code=500, detail=f"Failed to create order: {str(e)}")


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

    # Determine the correct cover product tier
    price = order["price"]
    tier_name, tier_info = get_tier_for_price(price)
    variant_gid = tier_info.get("variant_gid")

    if not variant_gid:
        logger.error(
            "No variant GID configured for tier '%s'. Cover products may not be initialized.",
            tier_name,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Cover product '{tier_info['name']}' is not configured. Please initialize products first.",
        )

    try:
        # Create Shopify cart and get checkout URL
        cart = await create_checkout_cart(variant_gid, order_id)
        checkout_url = cart.get("checkoutUrl")
        cart_id = cart.get("id")

        if not checkout_url:
            raise Exception("No checkout URL returned from Shopify")

        # Update order in database
        update_order(
            order_id,
            status="checkout_created",
            checkout_url=checkout_url,
            shopify_cart_id=cart_id,
            cover_product_id=tier_name,
        )

        logger.info(
            "Checkout created for order %s: %s",
            order_id,
            checkout_url,
        )
        return {"checkout_url": checkout_url}

    except Exception as e:
        logger.error("Failed to create checkout for order %s: %s", order_id, e)
        raise HTTPException(
            status_code=502,
            detail=f"Failed to create Shopify checkout: {str(e)}",
        )


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

        logger.info(
            "Shopify order created: id=%s, cart_token=%s, total=%s",
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
                logger.info("Order %s updated to 'paid'", order_id)
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


@app.get("/api/orders/{order_id}")
async def get_order_api(order_id: str):
    """Get order details via API."""
    order = get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@app.get("/api/orders")
async def list_orders_api(limit: int = 50, offset: int = 0):
    """List all orders."""
    orders = list_orders(limit=limit, offset=offset)
    return {"orders": orders, "count": len(orders)}
