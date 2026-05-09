#!/usr/bin/env python3
"""
sync_feishu.py — 同步B站订单到飞书多维表
订单创建时写入飞书，状态变更时更新飞书
"""
import json
import logging
import time
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# === 飞书配置 ===
FEISHU_APP_ID = "cli_a9619830e2fadcd1"
FEISHU_APP_SECRET = "kXdwL8yJZCDo9kwych0npgZ5W078RRkK"
APP_TOKEN = "NeYhbLvYaaFvJesSz8wcdBqhnRd"
TABLE_ID = "tblLLOUHq3AcIkLy"

BASE_URL = "https://open.feishu.cn/open-apis"

# Token 缓存
_token_cache: dict = {"token": "", "expires_at": 0}


async def _get_token() -> str:
    """获取飞书 tenant_access_token，带缓存自动刷新"""
    now = time.time()
    if _token_cache["token"] and now < _token_cache["expires_at"] - 60:
        return _token_cache["token"]

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            f"{BASE_URL}/auth/v3/tenant_access_token/internal",
            json={"app_id": FEISHU_APP_ID, "app_secret": FEISHU_APP_SECRET},
        )
        data = resp.json()
        _token_cache["token"] = data["tenant_access_token"]
        _token_cache["expires_at"] = now + data.get("expire", 7200)
        logger.info("Feishu token refreshed, expires in %ds", data.get("expire", 7200))
        return _token_cache["token"]


def _format_items(items: list) -> str:
    """格式化产品信息为可读文本"""
    if not items:
        return ""
    lines = []
    for item in items:
        name = item.get("product_name", item.get("variant_summary", "未知产品"))
        price = item.get("price", 0)
        summary = item.get("variant_summary", "")
        sku = item.get("sku", "")
        line = f"• {name}"
        if summary:
            line += f" ({summary})"
        if sku:
            line += f" [{sku}]"
        line += f" — ${price}"
        lines.append(line)
    return "\n".join(lines)


async def sync_order_created(
    session_id: str,
    phone: str,
    total_price: float,
    items: list,
    status: str = "pending",
    order_id: Optional[int] = None,
    action_urls: Optional[dict] = None,
    checkout_url: Optional[str] = None,
) -> Optional[str]:
    """订单创建时写入飞书多维表，返回飞书 record_id"""
    try:
        token = await _get_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        fields = {
            "文本": str(order_id or session_id)[:190],
            "session_id": session_id,
            "产品信息": _format_items(items),
            "总价": total_price,
            "客户手机": phone,
            "状态": status,
            "创建时间": int(time.time()),
        }
        if action_urls:
            fields["操作"] = (
                "取消: " + action_urls.get("cancel", "") + "\n"
                "刷新: " + action_urls.get("refresh", "") + "\n"
                "查看: " + action_urls.get("view", "")
            )
        if checkout_url:
            fields["结算链接"] = checkout_url

        record = {"fields": fields}

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{BASE_URL}/bitable/v1/apps/{APP_TOKEN}/tables/{TABLE_ID}/records",
                headers=headers,
                json=record,
            )
            data = resp.json()
            if data.get("code") == 0:
                record_id = data["data"]["record"]["record_id"]
                logger.info("Feishu order created: session=%s record=%s", session_id, record_id)
                return record_id
            else:
                logger.warning(
                    "Feishu create failed: code=%s msg=%s",
                    data.get("code"), data.get("msg"),
                )
                return None
    except Exception as e:
        logger.error("Feishu sync created error: %s", e)
        return None


async def sync_order_updated(
    session_id: str,
    status: str,
    shopify_order_id: Optional[str] = None,
    checkout_url: Optional[str] = None,
    feishu_record_id: Optional[str] = None,
):
    """订单状态变更时更新飞书记录"""
    if not feishu_record_id:
        logger.warning("No feishu_record_id for session=%s, skipping update", session_id)
        return False

    try:
        token = await _get_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        update_fields = {"状态": status}
        if shopify_order_id:
            update_fields["Shopify订单号"] = shopify_order_id
        if checkout_url:
            update_fields["结算链接"] = checkout_url

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.put(
                f"{BASE_URL}/bitable/v1/apps/{APP_TOKEN}/tables/{TABLE_ID}/records/{feishu_record_id}",
                headers=headers,
                json={"fields": update_fields},
            )
            data = resp.json()
            if data.get("code") == 0:
                logger.info(
                    "Feishu updated: session=%s status=%s shopify=%s",
                    session_id, status, shopify_order_id or "-",
                )
                return True
            else:
                logger.warning(
                    "Feishu update failed: code=%s msg=%s",
                    data.get("code"), data.get("msg"),
                )
                return False
    except Exception as e:
        logger.error("Feishu sync updated error: %s", e)
        return False
