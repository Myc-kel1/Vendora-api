"""
Cart Schemas.

Pydantic models for cart request bodies and API responses.

Request models (what the client sends):
  CartItemAdd     — add a product to cart (product_id + quantity)
  CartItemUpdate  — set a new absolute quantity for an existing item

Response models (what the API returns):
  CartItemResponse — single line item with computed subtotal
  CartResponse     — full cart with all items and grand total

Design decisions:
  - quantity in CartItemAdd uses gt=0 (greater-than, not gte) so
    zero is rejected at the schema layer before hitting the service
  - CartItemUpdate also uses gt=0 — to remove an item, use DELETE
  - subtotal and total are Decimal for exact monetary arithmetic
  - CartResponse always includes ALL items — there is no pagination
    on the cart (cart size is capped at 20 items by the service layer)
"""
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class CartItemAdd(BaseModel):
    """Request body for POST /cart/add."""
    product_id: UUID = Field(description="UUID of the product to add")
    quantity: int = Field(
        ...,
        gt=0,
        description="Number of units to add. Must be at least 1. "
                    "If the product is already in the cart, this quantity "
                    "is added to the existing quantity (merge).",
    )


class CartItemUpdate(BaseModel):
    """Request body for PATCH /cart/{item_id}."""
    quantity: int = Field(
        ...,
        gt=0,
        description="New absolute quantity for this cart item. "
                    "Replaces the current quantity entirely. "
                    "Must be at least 1 — use DELETE /cart/{item_id} to remove.",
    )


class CartItemResponse(BaseModel):
    """A single product line in the cart response."""
    id: UUID = Field(description="Cart item UUID (use this for PATCH and DELETE)")
    product_id: UUID = Field(description="The product's UUID")
    product_name: str = Field(description="Product name at time of cart fetch")
    product_price: Decimal = Field(description="Current product unit price")
    quantity: int = Field(description="Number of units in the cart")
    subtotal: Decimal = Field(
        description="product_price × quantity — computed server-side"
    )

    model_config = {"from_attributes": True}


class CartResponse(BaseModel):
    """
    Full cart response including all items and grand total.

    Returned by all cart endpoints (GET, POST /add, PATCH, DELETE).
    """
    id: UUID = Field(description="Cart UUID")
    user_id: str = Field(description="Owner's user UUID")
    items: list[CartItemResponse] = Field(
        description="All items currently in the cart. Empty list if cart is empty."
    )
    total: Decimal = Field(
        description="Sum of all item subtotals. Zero for an empty cart."
    )
