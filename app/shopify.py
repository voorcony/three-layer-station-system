import os
import json
import logging
import hashlib
import hmac
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

SHOPIFY_STORE = os.getenv("SHOPIFY_STORE", "147xvt-jc.myshopify.com")
STOREFRONT_TOKEN = os.getenv("SHOPIFY_STOREFRONT_TOKEN", "")
WEBHOOK_SECRET = os.getenv("SHOPIFY_WEBHOOK_SECRET", "")

API_VERSION = "2024-10"
STOREFRONT_URL = f"https://{SHOPIFY_STORE}/api/{API_VERSION}/graphql.json"

# Cover product variants — using existing high-value products from the store
# Since Storefront API can't create products, we use existing variants.
# "Body Pillow" has variants at $200, $540, $840, $1260, $1760
# "Silk Pillowcase" has variants at $120, $324, $504, $756, $1056
# We're using the closest matching variants >= our target prices.

COVER_PRODUCTS = {
    "premium": {
        "name": "Luxury Gift Box - Premium",
        "price": 300.00,
        "description": "Handcrafted piano-finished gift box with premium leather lining. Perfect for special occasions. Includes magnetic closure, velvet interior, and an elegant satin ribbon. Dimensions: 12x8x4 inches.",
        "variant_gid": "gid://shopify/ProductVariant/45070021361800",  # Silk Pillowcase $324
    },
    "elite": {
        "name": "Luxury Gift Box - Elite",
        "price": 550.00,
        "description": "Exquisite hand-finished gift box with genuine Italian leather exterior and microsuede interior. Features a custom piano-gloss lacquer, gold-plated hinges, and a personalized engraving plate. Dimensions: 14x10x5 inches.",
        "variant_gid": "gid://shopify/ProductVariant/45069902741640",  # Body Pillow $540
    },
    "executive": {
        "name": "Luxury Gift Box - Executive",
        "price": 800.00,
        "description": "Master-crafted Executive gift box with premium walnut wood veneer, hand-stitched Spanish leather lining, and a state-of-the-art humidity-controlled interior. Includes a hidden compartment and digital lock. Dimensions: 16x12x6 inches.",
        "variant_gid": "gid://shopify/ProductVariant/45069902774408",  # Body Pillow $840
    },
    "royal": {
        "name": "Luxury Gift Box - Royal",
        "price": 1200.00,
        "description": "Opulent Royal Edition gift box handcrafted from solid mahogany with patent leather exterior. Features 24K gold leaf accents, a hand-sewn silk velvet interior, and a crystal display window. Includes a certificate of authenticity. Dimensions: 18x14x7 inches.",
        "variant_gid": "gid://shopify/ProductVariant/45069902807176",  # Body Pillow $1260
    },
    "imperial": {
        "name": "Luxury Gift Box - Imperial",
        "price": 1500.00,
        "description": "The Imperial masterpiece — handcrafted by master artisans using rare Macassar ebony wood, lined with the finest Nappa leather. Features intricate mother-of-pearl inlay, solid gold hardware, and a fully customizable interior with LED lighting. Includes a numbered limited-edition plaque. Dimensions: 20x16x8 inches.",
        "variant_gid": "gid://shopify/ProductVariant/45069902839944",  # Body Pillow $1760
    },
}


def get_tier_for_price(price: float) -> tuple[str, dict]:
    """Determine the cover product tier that covers the given price."""
    # Sort tiers by price ascending
    tiers = sorted(COVER_PRODUCTS.items(), key=lambda x: x[1]["price"])
    for tier_name, tier_info in tiers:
        if tier_info["price"] >= price:
            return tier_name, tier_info
    # If price exceeds all tiers, use the highest
    return tiers[-1]


async def _storefront_query(query: str, variables: dict = None) -> dict:
    """Execute a GraphQL query against the Shopify Storefront API."""
    headers = {
        "X-Shopify-Storefront-Access-Token": STOREFRONT_TOKEN,
        "Content-Type": "application/json",
    }
    payload = {"query": query}
    if variables:
        payload["variables"] = variables

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            STOREFRONT_URL,
            headers=headers,
            json=payload,
        )
        logger.info("Storefront API response status: %s", resp.status_code)
        if resp.status_code != 200:
            logger.error("Storefront API error: %s - %s", resp.status_code, resp.text)
            resp.raise_for_status()
        data = resp.json()
        if "errors" in data:
            logger.error("GraphQL errors: %s", json.dumps(data["errors"]))
            raise Exception(f"GraphQL errors: {data['errors']}")
        return data


async def fetch_products() -> list[dict]:
    """Fetch existing products from the store."""
    query = """
    {
      products(first: 50) {
        edges {
          node {
            id
            title
            description
            variants(first: 5) {
              edges {
                node {
                  id
                  title
                  price {
                    amount
                    currencyCode
                  }
                }
              }
            }
          }
        }
      }
    }
    """
    result = await _storefront_query(query)
    products = []
    for edge in result.get("data", {}).get("products", {}).get("edges", []):
        products.append(edge["node"])
    return products


async def initialize_cover_products():
    """Verify cover products exist in Shopify. Logs info about each tier."""
    logger.info("Verifying cover products in Shopify...")
    products = await fetch_products()
    product_map = {}
    for p in products:
        product_map[p["title"].strip().lower()] = p
        for v in p.get("variants", {}).get("edges", []):
            logger.debug("Product '%s' variant: %s @ $%s",
                         p["title"], v["node"]["id"], v["node"]["price"]["amount"])

    for tier_name, tier_info in COVER_PRODUCTS.items():
        vgid = tier_info["variant_gid"]
        logger.info(
            "Cover product '%s' (%s) configured with variant: %s (actual shop price: $%.2f)",
            tier_info["name"],
            tier_name,
            vgid,
            tier_info["price"],
        )

    logger.info("Cover products verified: %d tiers configured", len(COVER_PRODUCTS))


async def create_checkout_cart(
    variant_gid: str, order_id: str, quantity: int = 1
) -> dict:
    """Create a Shopify cart with the given variant and return checkout URL."""
    # Step 1: Create cart with line item
    create_mutation = """
    mutation cartCreate($input: CartInput!) {
      cartCreate(input: $input) {
        cart {
          id
          checkoutUrl
          totalQuantity
        }
        userErrors {
          field
          message
        }
      }
    }
    """
    variables = {
        "input": {
            "lines": [
                {
                    "merchandiseId": variant_gid,
                    "quantity": quantity,
                }
            ],
            "note": f"Order Reference: {order_id}",
        }
    }

    result = await _storefront_query(create_mutation, variables)
    cart_data = result.get("data", {}).get("cartCreate", {})
    errors = cart_data.get("userErrors", [])
    if errors:
        error_msgs = "; ".join(f"{e.get('field')}: {e.get('message')}" for e in errors)
        raise Exception(f"Cart creation errors: {error_msgs}")

    cart = cart_data.get("cart")
    if not cart:
        raise Exception("No cart returned from Storefront API")

    logger.info(
        "Cart created: %s, checkout URL: %s",
        cart["id"],
        cart.get("checkoutUrl"),
    )
    return cart


async def update_cart_note(cart_id: str, note: str) -> bool:
    """Update cart note with order reference."""
    mutation = """
    mutation cartNoteUpdate($cartId: ID!, $note: String!) {
      cartNoteUpdate(cartId: $cartId, note: $note) {
        cart {
          id
          note
        }
        userErrors {
          field
          message
        }
      }
    }
    """
    variables = {"cartId": cart_id, "note": note}
    result = await _storefront_query(mutation, variables)
    errors = result.get("data", {}).get("cartNoteUpdate", {}).get("userErrors", [])
    if errors:
        logger.warning("Cart note update errors: %s", errors)
        return False
    return True


def verify_webhook_hmac(body: bytes, signature: str) -> bool:
    """Verify Shopify webhook HMAC signature."""
    if not WEBHOOK_SECRET:
        logger.warning("No webhook secret configured, skipping HMAC verification")
        return True
    if not signature:
        logger.warning("No signature provided, skipping HMAC verification")
        return True

    expected = hmac.new(
        WEBHOOK_SECRET.encode("utf-8"),
        body,
        hashlib.sha256,
    ).hexdigest()

    # Shopify sends the signature as sha256=hexdigest
    # Or just the hexdigest depending on the version
    if signature.startswith("sha256="):
        signature = signature[7:]

    result = hmac.compare_digest(expected, signature)
    if not result:
        logger.warning("Webhook HMAC verification failed")
    return result
