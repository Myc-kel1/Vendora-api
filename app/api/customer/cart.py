"""
Customer — Cart Endpoints.

Handles all cart operations for the authenticated buyer:
  - View current cart with computed totals
  - Add item (validates stock, merges duplicates)
  - Update item quantity (absolute set, re-validates stock)
  - Remove item (scoped to user's cart — prevents cross-user deletion)

All routes require a valid JWT (get_current_user dependency).
Cart is persistent (DB-backed), one cart per user, auto-created on first use.
"""
from uuid import UUID

from fastapi import APIRouter, Depends

from app.dependencies.auth import get_current_user
from app.schemas.cart import CartItemAdd, CartItemUpdate, CartResponse
from app.schemas.user import CurrentUser
from app.services.cart_service import CartService

router = APIRouter(prefix="/cart", tags=["Customer — Cart"])


@router.get("", response_model=CartResponse)
def get_cart(
    current_user: CurrentUser = Depends(get_current_user),
    service: CartService = Depends(CartService),
):
    """
    Get the authenticated user's cart with all items and computed totals.

    - Auto-creates an empty cart if the user has never added anything
    - Returns subtotals per item and grand total
    - Returns 401 if unauthenticated
    """
    return service.get_cart(current_user.id)


@router.post("/add", response_model=CartResponse, status_code=201)
def add_to_cart(
    payload: CartItemAdd,
    current_user: CurrentUser = Depends(get_current_user),
    service: CartService = Depends(CartService),
):
    """
    Add a product to the cart.

    Business rules enforced:
    - Product must exist (404 if not)
    - quantity must be >= 1 (validated by Pydantic)
    - Stock must cover the requested quantity (409 StockError if not)
    - If product is already in cart, quantities are merged and the
      combined total is re-validated against stock
    - Cart is capped at 20 distinct product lines (422 if exceeded)

    Returns the full updated cart.
    """
    return service.add_item(current_user.id, payload)


@router.patch("/{item_id}", response_model=CartResponse)
def update_cart_item(
    item_id: UUID,
    payload: CartItemUpdate,
    current_user: CurrentUser = Depends(get_current_user),
    service: CartService = Depends(CartService),
):
    """
    Set an exact quantity for a cart item.

    Use this to replace the current quantity rather than increment it.
    Stock is re-validated against the new quantity before saving.

    - item_id must belong to the user's own cart (403 if not)
    - quantity must be >= 1 (use DELETE to remove)
    - Returns 404 if item_id does not exist in the user's cart
    """
    return service.update_item(current_user.id, str(item_id), payload.quantity)


@router.delete("/{item_id}", response_model=CartResponse)
def remove_from_cart(
    item_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    service: CartService = Depends(CartService),
):
    """
    Remove a specific item from the cart.

    The removal is scoped to the user's own cart_id — a user cannot
    remove items belonging to a different user's cart even if they
    know the item_id UUID.

    Returns the updated cart after removal.
    """
    return service.remove_item(current_user.id, str(item_id))
