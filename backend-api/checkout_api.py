#!/usr/bin/env python3
"""
checkout_api.py — Thin HTTP proxy to B站 (43.154.181.44)

启动: uvicorn checkout_api:app --host 127.0.0.1 --port 8099
"""
import os
import sys
from datetime import datetime

from fastapi import FastAPI, Request, Response
from pydantic import BaseModel
import httpx

app = FastAPI(title="Landing Checkout API (Proxy)", version="2.0.0")

B_API_BASE = "http://43.154.181.44"
B_API_KEY = os.getenv("B_API_KEY", "apk_b9a7c3d1e5f80")
HTTP_TIMEOUT = 15.0


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


def _b_headers(extra: dict | None = None) -> dict:
    headers = {"X-Api-Key": B_API_KEY}
    if extra:
        headers.update(extra)
    return headers


@app.post("/api/create_checkout")
async def create_checkout(req: CheckoutRequest):
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        resp = await client.post(
            f"{B_API_BASE}/api/create_checkout",
            json=req.dict(),
            headers=_b_headers({"Content-Type": "application/json"}),
        )
    print(f"[proxy] create_checkout {req.session_id} → {resp.status_code}", file=sys.stderr)
    return Response(
        content=resp.content,
        status_code=resp.status_code,
        media_type=resp.headers.get("content-type"),
    )


@app.get("/api/order/{session_id}")
async def get_order(session_id: str):
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        resp = await client.get(
            f"{B_API_BASE}/api/orders",
            params={"session_id": session_id},
            headers=_b_headers(),
        )
    return Response(
        content=resp.content,
        status_code=resp.status_code,
        media_type=resp.headers.get("content-type"),
    )


@app.post("/api/webhook/shopify")
async def shopify_webhook(request: Request):
    body = await request.body()
    # Forward original headers but override host/auth-related; add B站 API key.
    forward_headers = {
        k: v
        for k, v in request.headers.items()
        if k.lower() not in ("host", "content-length")
    }
    forward_headers["X-Api-Key"] = B_API_KEY

    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        resp = await client.post(
            f"{B_API_BASE}/api/webhook/shopify",
            content=body,
            headers=forward_headers,
        )
    return Response(
        content=resp.content,
        status_code=resp.status_code,
        media_type=resp.headers.get("content-type"),
    )


@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}
