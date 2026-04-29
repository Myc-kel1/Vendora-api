"""Customer — Orders."""
from uuid import UUID
from fastapi import APIRouter, Depends, Query
from app.dependencies.auth import get_current_user
from app.schemas.order import OrderListResponse, OrderResponse
from app.schemas.user import CurrentUser
from app.services.order_service import OrderService

router = APIRouter(prefix="/orders", tags=["Customer — Orders"])


@router.post("", response_model=OrderResponse, status_code=201)
def place_order(
    current_user: CurrentUser = Depends(get_current_user),
    service: OrderService = Depends(OrderService),
):
    return service.place_order(current_user.id)


@router.get("/my-orders", response_model=OrderListResponse)
def get_my_orders(
    page:      int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    current_user: CurrentUser = Depends(get_current_user),
    service: OrderService = Depends(OrderService),
):
    return service.get_my_orders(current_user.id, page=page, page_size=page_size)


@router.get("/{order_id}", response_model=OrderResponse)
def get_order(
    order_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    service: OrderService = Depends(OrderService),
):
    return service.get_order_for_user(str(order_id), user_id=current_user.id)


@router.post("/{order_id}/cancel", response_model=OrderResponse)
def cancel_order(
    order_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    service: OrderService = Depends(OrderService),
):
    return service.cancel_order(str(order_id), user_id=current_user.id)