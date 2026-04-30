from pydantic import BaseModel, Field
from typing import Optional


class OrderCreateRequest(BaseModel):
    product_name: str
    product_spec: Optional[str] = ""
    product_image_url: Optional[str] = ""
    price: float
    customer_name: Optional[str] = ""
    customer_phone: Optional[str] = ""


class OrderResponse(BaseModel):
    order_id: str
    page_url: str


class CheckoutResponse(BaseModel):
    checkout_url: str


class ShopPayload(BaseModel):
    """

    Shopify webhook payload is raw JSON; we only extract needed fields.
    """
    id: Optional[int] = None
    order_number: Optional[int] = None
    cart_token: Optional[str] = None
    note: Optional[str] = None
    total_price: Optional[str] = None
    customer: Optional[dict] = None
    line_items: Optional[list] = None
