"""Customer — Cart."""
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
    return service.get_cart(current_user.id)


@router.post("/add", response_model=CartResponse, status_code=201)
def add_to_cart(
    payload: CartItemAdd,
    current_user: CurrentUser = Depends(get_current_user),
    service: CartService = Depends(CartService),
):
    return service.add_item(current_user.id, payload)


@router.patch("/{item_id}", response_model=CartResponse)
def update_cart_item(
    item_id: UUID,
    payload: CartItemUpdate,
    current_user: CurrentUser = Depends(get_current_user),
    service: CartService = Depends(CartService),
):
    return service.update_item(current_user.id, str(item_id), payload.quantity)


@router.delete("/{item_id}", response_model=CartResponse)
def remove_from_cart(
    item_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    service: CartService = Depends(CartService),
):
    return service.remove_item(current_user.id, str(item_id))