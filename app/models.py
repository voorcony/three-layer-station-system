from pydantic import BaseModel, Field
from typing import Optional


class OrderCreateRequest(BaseModel):
    product_name: str
    product_spec: Optional[str] = ""
    product_image_url: Optional[str] = ""
    price: float  # 订单金额/A站价格
    customer_name: Optional[str] = ""
    customer_phone: Optional[str] = ""


class OrderResponse(BaseModel):
    order_id: str
    page_url: str
    unit_quantity: int = 0
    unit_price: float = 99.0
    discount_amount: float = 0.0


class CheckoutResponse(BaseModel):
    checkout_url: str
    discount_code: str = ''
    unit_quantity: int = 0
    unit_price: float = 99.0
    discount_amount: float = 0.0


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


class AdminOrderUpdate(BaseModel):
    status: Optional[str] = None
    tracking_number: Optional[str] = None
    notes: Optional[str] = None


class AdminStatusUpdate(BaseModel):
    status: str
