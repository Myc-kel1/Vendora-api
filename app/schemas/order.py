from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID
from pydantic import BaseModel

OrderStatus = Literal["pending", "paid", "failed", "cancelled"]


class OrderItemResponse(BaseModel):
    id:           UUID
    product_id:   UUID
    product_name: str
    quantity:     int
    price:        Decimal   # price snapshot at order time
    subtotal:     Decimal
    model_config = {"from_attributes": True}


class OrderResponse(BaseModel):
    id:           UUID
    user_id:      str
    status:       OrderStatus
    total_amount: Decimal
    items:        list[OrderItemResponse]
    created_at:   datetime
    model_config = {"from_attributes": True}


class OrderListResponse(BaseModel):
    items: list[OrderResponse]
    total: int


class OrderStatusUpdate(BaseModel):
    status: OrderStatus