from decimal import Decimal
from uuid import UUID
from pydantic import BaseModel, Field


class CartItemAdd(BaseModel):
    product_id: UUID
    quantity:   int = Field(..., gt=0, description="Must be at least 1")


class CartItemUpdate(BaseModel):
    quantity: int = Field(..., gt=0, description="New absolute quantity, min 1")


class CartItemResponse(BaseModel):
    id:            UUID
    product_id:    UUID
    product_name:  str
    product_price: Decimal
    quantity:      int
    subtotal:      Decimal
    image_url:     str | None = None   # product image shown in cart
    model_config = {"from_attributes": True}


class CartResponse(BaseModel):
    id:      UUID
    user_id: str
    items:   list[CartItemResponse]
    total:   Decimal