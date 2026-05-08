import os
import json
import logging
import hashlib
import hmac
from math import ceil
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

SHOPIFY_STORE = os.getenv("SHOPIFY_STORE", "147xvt-jc.myshopify.com")
STOREFRONT_TOKEN = os.getenv("SHOPIFY_STOREFRONT_TOKEN", "")
WEBHOOK_SECRET = os.getenv("SHOPIFY_WEBHOOK_SECRET", "")

API_VERSION = "2024-10"
STOREFRONT_URL = f"https://{SHOPIFY_STORE}/api/{API_VERSION}/graphql.json"

# ---------------------------------------------------------------------------
# Legacy fallback: hardcoded cover products using existing Body Pillow variants
# These are used ONLY if the "Luxury Gift Collection" product doesn't exist yet
# ---------------------------------------------------------------------------
LEGACY_COVER_PRODUCTS = {
    "premium": {
        "name": "Luxury Gift Box - Premium",
        "price": 300.00,
        "description": "Handcrafted piano-finished gift box with premium leather lining.",
        "variant_gid": "gid://shopify/ProductVariant/45070021361800",  # Silk Pillowcase $324
    },
    "elite": {
        "name": "Luxury Gift Box - Elite",
        "price": 550.00,
        "description": "Exquisite hand-finished gift box with genuine Italian leather.",
        "variant_gid": "gid://shopify/ProductVariant/45069902741640",  # Body Pillow $540
    },
    "executive": {
        "name": "Luxury Gift Box - Executive",
        "price": 800.00,
        "description": "Master-crafted Executive gift box with premium walnut wood veneer.",
        "variant_gid": "gid://shopify/ProductVariant/45069902774408",  # Body Pillow $840
    },
    "royal": {
        "name": "Luxury Gift Box - Royal",
        "price": 1200.00,
        "description": "Opulent Royal Edition gift box handcrafted from solid mahogany.",
        "variant_gid": "gid://shopify/ProductVariant/45069902807176",  # Body Pillow $1260
    },
    "imperial": {
        "name": "Luxury Gift Box - Imperial",
        "price": 1500.00,
        "description": "The Imperial masterpiece handcrafted by master artisans.",
        "variant_gid": "gid://shopify/ProductVariant/45069902839944",  # Body Pillow $1760
    },
}

# ---------------------------------------------------------------------------
# Cached luxury variants (lazy-loaded at startup)
# ---------------------------------------------------------------------------
_luxury_variants: list[dict] = []
_luxury_variants_loaded = False


# ---------------------------------------------------------------------------
# Core helper: execute Storefront API queries
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Luxury Gift Collection product — dynamic variant fetching
# ---------------------------------------------------------------------------
LUXURY_PRODUCT_TITLE = "Luxury Gift Collection"

# The 20 desired tier prices
TIER_PRICES = [100, 200, 300, 400, 500, 600, 700, 800, 900, 1000,
               1100, 1200, 1300, 1400, 1500, 1600, 1700, 1800, 1900, 2000]


async def fetch_luxury_variants() -> list[dict]:
    """
    Fetch ALL variants from the 'Luxury Gift Collection' product.
    Searches by exact title match (case-insensitive).
    Returns a list of dicts with keys: id, title, price (float), currencyCode.
    Returns empty list if product not found.
    """
    query = """
    {
      products(first: 50) {
        edges {
          node {
            id
            title
            variants(first: 100) {
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
    products = result.get("data", {}).get("products", {}).get("edges", [])

    for edge in products:
        node = edge["node"]
        title = node.get("title", "").strip().lower()
        if title == LUXURY_PRODUCT_TITLE.strip().lower():
            variants = []
            for ve in node.get("variants", {}).get("edges", []):
                vn = ve["node"]
                variants.append({
                    "id": vn["id"],
                    "title": vn["title"],
                    "price": float(vn["price"]["amount"]),
                    "currencyCode": vn["price"]["currencyCode"],
                })
            logger.info(
                "Found Luxury Gift Collection product with %d variants",
                len(variants),
            )
            return variants

    logger.warning(
        "Luxury Gift Collection product not found in store. "
        "Please create it manually in Shopify Admin with 20 variants "
        "at prices: %s", TIER_PRICES
    )
    return []


async def try_refresh_luxury_variants() -> bool:
    """
    Attempt to (re)load luxury variants from Shopify.
    Returns True if successful, False if not found.
    """
    global _luxury_variants, _luxury_variants_loaded
    try:
        variants = await fetch_luxury_variants()
        if variants:
            _luxury_variants = sorted(variants, key=lambda v: v["price"])
            _luxury_variants_loaded = True
            logger.info(
                "Loaded %d luxury variants: %s",
                len(_luxury_variants),
                [(v["price"], v["title"]) for v in _luxury_variants],
            )
            return True
        else:
            _luxury_variants = []
            _luxury_variants_loaded = False
            return False
    except Exception as e:
        logger.error("Failed to fetch luxury variants: %s", e)
        _luxury_variants = []
        _luxury_variants_loaded = False
        return False


def select_variant_for_price(price: float) -> dict | None:
    """
    Select the best matching variant for a given watch price.
    Strategy: find the variant whose price is >= the watch price (closest match).
    If all variants are below the price, use the most expensive one.
    Returns None if no variants are available.
    """
    global _luxury_variants
    if not _luxury_variants:
        return None

    # Sort ascending by price
    sorted_variants = sorted(_luxury_variants, key=lambda v: v["price"])

    for v in sorted_variants:
        if v["price"] >= price:
            return v

    # Price exceeds all variants — return the most expensive one
    return sorted_variants[-1]


def get_legacy_tier_for_price(price: float) -> tuple[str, dict]:
    """Fallback: use legacy hardcoded tier system."""
    tiers = sorted(LEGACY_COVER_PRODUCTS.items(), key=lambda x: x[1]["price"])
    for tier_name, tier_info in tiers:
        if tier_info["price"] >= price:
            return tier_name, tier_info
    return tiers[-1]


# ---------------------------------------------------------------------------
# Legacy: fetch products (kept for compatibility)
# ---------------------------------------------------------------------------
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
    """
    Initialize: try to load Luxury Gift Collection variants first.
    If not found, log instructions for manual creation and fall back to legacy.
    """
    global _luxury_variants, _luxury_variants_loaded
    logger.info("Initializing cover products...")

    success = await try_refresh_luxury_variants()

    if success:
        logger.info(
            "Using Luxury Gift Collection with %d dynamic variants",
            len(_luxury_variants),
        )
    else:
        logger.warning(
            "Luxury Gift Collection not found. "
            "Falling back to legacy hardcoded cover products. "
            "To enable dynamic pricing, please create a product named "
            "'Luxury Gift Collection' in Shopify Admin with these 20 variants:"
        )
        for p in TIER_PRICES:
            logger.warning("  - $%d Tier ($%d.00)", p, p)
        logger.info("Using %d legacy tiers as fallback", len(LEGACY_COVER_PRODUCTS))


async def get_tier_label(price: float) -> str:
    """
    Get the tier label / variant title for a given watch price.
    Tries luxury variants first, falls back to legacy.
    """
    variant = select_variant_for_price(price)
    if variant:
        return variant.get("title", f"${variant['price']:.0f} Tier")
    tier_name, _ = get_legacy_tier_for_price(price)
    return LEGACY_COVER_PRODUCTS[tier_name]["name"]


async def get_variant_for_checkout(price: float) -> dict:
    """
    Get the variant GID and info to use for creating a checkout.
    Returns dict with keys: variant_gid, variant_title, tier_name, price
    """
    variant = select_variant_for_price(price)
    if variant:
        return {
            "variant_gid": variant["id"],
            "variant_title": variant["title"],
            "tier_name": f"luxury_{variant['price']:.0f}",
            "price": variant["price"],
        }

    # Fallback to legacy
    tier_name, tier_info = get_legacy_tier_for_price(price)
    return {
        "variant_gid": tier_info["variant_gid"],
        "variant_title": tier_info["name"],
        "tier_name": tier_name,
        "price": tier_info["price"],
    }


# ---------------------------------------------------------------------------
# Unit-price helpers
# ---------------------------------------------------------------------------
def calculate_price_match(price: float, unit_price=None) -> dict:
    if unit_price is None:
        unit_price = os.getenv('UNIT_PRICE', 99)
    qty = ceil(price / float(unit_price))
    total_before = qty * float(unit_price)
    discount = round(total_before - price, 2)
    return {
        'qty': qty,
        'unit_price': float(unit_price),
        'total_before': total_before,
        'discount': discount,
    }


def get_unit_variant_gid() -> str:
    gid = os.getenv('UNIT_VARIANT_GID', '')
    if not gid:
        raise Exception('UNIT_VARIANT_GID not configured')
    return gid


# ---------------------------------------------------------------------------
# Cart / checkout creation
# ---------------------------------------------------------------------------
async def create_checkout_cart(
    variant_gid: str, order_id: str, quantity: int = 1, discount_code: Optional[str] = None
) -> dict:
    """Create a Shopify cart with the given variant and return checkout URL."""
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
    if discount_code:
        variables["input"]["discountCodes"] = [discount_code]

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


# ---------------------------------------------------------------------------
# Webhook HMAC verification
# ---------------------------------------------------------------------------
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

    if signature.startswith("sha256="):
        signature = signature[7:]

    result = hmac.compare_digest(expected, signature)
    if not result:
        logger.warning("Webhook HMAC verification failed")
    return result


# ---------------------------------------------------------------------------
# Expose a unified function that main.py uses
# ---------------------------------------------------------------------------
# Keep backward-compatible reference
COVER_PRODUCTS = LEGACY_COVER_PRODUCTS

def get_tier_for_price(price: float) -> tuple[str, dict]:
    """
    Legacy compatibility wrapper.
    Returns (tier_name, tier_info) using the legacy system.
    """
    return get_legacy_tier_for_price(price)
