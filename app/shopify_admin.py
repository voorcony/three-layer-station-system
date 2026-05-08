import os
import json
import logging
from datetime import datetime, timedelta, timezone

import httpx

logger = logging.getLogger(__name__)

API_VERSION = "2024-10"


async def _admin_api_request(method: str, endpoint: str, data: dict = None) -> dict:
    """Execute a request against the Shopify Admin REST API."""
    admin_token = os.getenv("SHOPIFY_ADMIN_TOKEN", "")
    store = os.getenv("SHOPIFY_STORE", "")

    if not admin_token:
        raise Exception("SHOPIFY_ADMIN_TOKEN environment variable is not set")
    if not store:
        raise Exception("SHOPIFY_STORE environment variable is not set")

    url = f"https://{store}/admin/api/{API_VERSION}/{endpoint}"
    headers = {
        "X-Shopify-Access-Token": admin_token,
        "Content-Type": "application/json",
    }

    logger.info("Admin API request: %s %s", method, url)
    if data is not None:
        logger.info("Admin API request payload: %s", json.dumps(data))

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.request(
            method=method,
            url=url,
            headers=headers,
            json=data if data is not None else None,
        )

    logger.info("Admin API response status: %s", resp.status_code)

    if resp.status_code >= 400:
        logger.error(
            "Admin API error: %s - %s",
            resp.status_code,
            resp.text,
        )
        resp.raise_for_status()

    try:
        result = resp.json()
    except ValueError:
        logger.error("Failed to decode JSON response: %s", resp.text)
        raise Exception(f"Invalid JSON response from Admin API: {resp.text}")

    logger.info("Admin API response body: %s", json.dumps(result))
    return result


async def create_price_rule(amount: float, title: str) -> dict:
    """Create a one-time fixed-amount price rule via the Admin API."""
    now = datetime.now(timezone.utc)
    ends_at = now + timedelta(hours=24)

    value = f"-{amount}"

    payload = {
        "price_rule": {
            "title": title,
            "target_type": "line_item",
            "target_selection": "all",
            "allocation_method": "across",
            "value_type": "fixed_amount",
            "value": value,
            "customer_selection": "all",
            "usage_limit": 1,
            "once_per_customer": True,
            "starts_at": now.isoformat(),
            "ends_at": ends_at.isoformat(),
        }
    }

    result = await _admin_api_request("POST", "price_rules.json", data=payload)
    price_rule = result.get("price_rule")
    if not price_rule:
        raise Exception(f"Price rule creation returned no price_rule: {result}")

    price_rule_id = price_rule.get("id")
    logger.info("Created price rule id=%s title=%s value=%s", price_rule_id, title, value)

    return {
        "id": price_rule_id,
        "price_rule": price_rule,
    }


async def create_discount_code(price_rule_id: int, code: str) -> dict:
    """Attach a discount code string to an existing price rule."""
    endpoint = f"price_rules/{price_rule_id}/discount_codes.json"
    payload = {
        "discount_code": {
            "code": code,
        }
    }

    result = await _admin_api_request("POST", endpoint, data=payload)
    discount_code = result.get("discount_code")
    if not discount_code:
        raise Exception(f"Discount code creation returned no discount_code: {result}")

    logger.info(
        "Created discount code id=%s code=%s for price_rule_id=%s",
        discount_code.get("id"),
        discount_code.get("code"),
        price_rule_id,
    )
    return discount_code


async def create_one_time_discount(amount: float, code: str) -> dict:
    """Create a one-time discount: a price rule plus its associated discount code."""
    try:
        price_rule_result = await create_price_rule(
            amount=amount,
            title=code,
        )
        price_rule_id = price_rule_result["id"]
        price_rule = price_rule_result["price_rule"]

        discount_code = await create_discount_code(
            price_rule_id=price_rule_id,
            code=code,
        )

        logger.info(
            "Successfully created one-time discount: code=%s amount=%s price_rule_id=%s",
            code,
            amount,
            price_rule_id,
        )

        return {
            "price_rule": price_rule,
            "discount_code": discount_code,
            "code": code,
        }
    except Exception as e:
        logger.error(
            "Failed to create one-time discount (code=%s amount=%s): %s",
            code,
            amount,
            e,
        )
        raise Exception(f"Failed to create one-time discount: {e}") from e
