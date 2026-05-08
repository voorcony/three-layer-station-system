import json
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

WC_API_URL = "http://127.0.0.1:8080/wp-content/orders-api.php"
WC_API_KEY = "apk_b9a7c3d1e5f8024679b1a3c5d7e9f0b1"

_DEFAULT_TIMEOUT = 10.0
_HEADERS = {
    "X-API-Key": WC_API_KEY,
    "Content-Type": "application/json",
}


async def wc_create_order(
    session_id: str,
    customer_name: str,
    customer_phone: str,
    items: list[dict],
    total_price: Any,
) -> dict:
    """Create a new WooCommerce order keyed by session_id.

    POSTs to WC_API_URL?action=create.
    Returns a dict with success, order_id, session_id, status, total.
    Raises on critical failure (network error or non-2xx response).
    """
    payload = {
        "session_id": session_id,
        "customer_name": customer_name,
        "customer_phone": customer_phone,
        "items": items,
        "total_price": total_price,
    }

    logger.info("WC create order: session_id=%s total=%s", session_id, total_price)
    logger.debug("WC create payload: %s", json.dumps(payload, default=str))

    try:
        async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT) as client:
            resp = await client.post(
                WC_API_URL,
                params={"action": "create"},
                headers=_HEADERS,
                json=payload,
            )
    except httpx.HTTPError as e:
        logger.error("WC create order request failed for session_id=%s: %s", session_id, e)
        raise

    logger.info("WC create order response status=%s", resp.status_code)

    if resp.status_code >= 400:
        logger.error(
            "WC create order error session_id=%s status=%s body=%s",
            session_id,
            resp.status_code,
            resp.text,
        )
        resp.raise_for_status()

    try:
        result = resp.json()
    except ValueError:
        logger.error("WC create order: invalid JSON response: %s", resp.text)
        raise Exception(f"Invalid JSON response from WC API: {resp.text}")

    logger.info(
        "WC create order ok session_id=%s order_id=%s status=%s",
        session_id,
        result.get("order_id"),
        result.get("status"),
    )
    return result


async def wc_get_order(session_id: str) -> dict | None:
    """Fetch a WooCommerce order by session_id.

    GETs WC_API_URL?action=get&session_id=xxx.
    Returns the order dict, or None if the order does not exist (404).
    """
    logger.info("WC get order: session_id=%s", session_id)

    try:
        async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT) as client:
            resp = await client.get(
                WC_API_URL,
                params={"action": "get", "session_id": session_id},
                headers=_HEADERS,
            )
    except httpx.HTTPError as e:
        logger.error("WC get order request failed for session_id=%s: %s", session_id, e)
        return None

    if resp.status_code == 404:
        logger.info("WC get order: not found session_id=%s", session_id)
        return None

    if resp.status_code >= 400:
        logger.error(
            "WC get order error session_id=%s status=%s body=%s",
            session_id,
            resp.status_code,
            resp.text,
        )
        return None

    try:
        result = resp.json()
    except ValueError:
        logger.error("WC get order: invalid JSON response: %s", resp.text)
        return None

    logger.info("WC get order ok session_id=%s", session_id)
    return result


async def wc_update_order(session_id: str, **kwargs: Any) -> dict:
    """Update a WooCommerce order identified by session_id.

    POSTs to WC_API_URL?action=update.
    Accepted kwargs: shopify_order_id, status, checkout_url, cart_id.
    """
    allowed = {"shopify_order_id", "status", "checkout_url", "cart_id", "feishu_record_id"}
    updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}

    extra = set(kwargs) - allowed
    if extra:
        logger.warning("WC update order: ignoring unsupported fields: %s", sorted(extra))

    payload = {"session_id": session_id, **updates}

    logger.info("WC update order: session_id=%s fields=%s", session_id, sorted(updates.keys()))
    logger.debug("WC update payload: %s", json.dumps(payload, default=str))

    try:
        async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT) as client:
            resp = await client.post(
                WC_API_URL,
                params={"action": "update"},
                headers=_HEADERS,
                json=payload,
            )
    except httpx.HTTPError as e:
        logger.error("WC update order request failed for session_id=%s: %s", session_id, e)
        raise

    logger.info("WC update order response status=%s", resp.status_code)

    if resp.status_code >= 400:
        logger.error(
            "WC update order error session_id=%s status=%s body=%s",
            session_id,
            resp.status_code,
            resp.text,
        )
        resp.raise_for_status()

    try:
        result = resp.json()
    except ValueError:
        logger.error("WC update order: invalid JSON response: %s", resp.text)
        raise Exception(f"Invalid JSON response from WC API: {resp.text}")

    logger.info("WC update order ok session_id=%s", session_id)
    return result


async def wc_list_orders(limit: int = 50, status: str = "") -> list[dict]:
    """List WooCommerce orders.

    GETs WC_API_URL?action=list with limit and optional status filter.
    Returns a list of order dicts (empty list on error).
    """
    params: dict[str, Any] = {"action": "list", "limit": limit}
    if status:
        params["status"] = status

    logger.info("WC list orders: limit=%s status=%s", limit, status or "<any>")

    try:
        async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT) as client:
            resp = await client.get(WC_API_URL, params=params, headers=_HEADERS)
    except httpx.HTTPError as e:
        logger.error("WC list orders request failed: %s", e)
        return []

    if resp.status_code >= 400:
        logger.error(
            "WC list orders error status=%s body=%s",
            resp.status_code,
            resp.text,
        )
        return []

    try:
        result = resp.json()
    except ValueError:
        logger.error("WC list orders: invalid JSON response: %s", resp.text)
        return []

    if isinstance(result, dict):
        orders = result.get("orders") or result.get("data") or []
    elif isinstance(result, list):
        orders = result
    else:
        logger.error("WC list orders: unexpected response shape: %s", type(result).__name__)
        return []

    logger.info("WC list orders ok count=%d", len(orders))
    return orders
