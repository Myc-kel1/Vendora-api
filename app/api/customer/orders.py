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
    """
    Place an order from the current cart.

    - Cart must not be empty
    - Stock is re-validated at order time (double-check)
    - Stock is atomically deducted via SQL RPC (no overselling)
    - Cart is cleared on success
    - Returns the created order with status=pending
    """
    return service.place_order(current_user.id)


@router.get("/my-orders", response_model=OrderListResponse)
def get_my_orders(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    current_user: CurrentUser = Depends(get_current_user),
    service: OrderService = Depends(OrderService),
):
    """Get all orders for the authenticated user. Paginated, newest first."""
    return service.get_my_orders(current_user.id, page=page, page_size=page_size)


@router.get("/{order_id}", response_model=OrderResponse)
def get_order(
    order_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    service: OrderService = Depends(OrderService),
):
    """
    Get a single order by ID.

    - Returns 404 if the order does not exist
    - Returns 403 if the order belongs to a different user
    """
    return service.get_order_for_user(str(order_id), user_id=current_user.id)


@router.post("/{order_id}/cancel", response_model=OrderResponse)
def cancel_order(
    order_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    service: OrderService = Depends(OrderService),
):
    """
    Cancel a pending order.

    - Only orders with status=pending can be cancelled by the customer
    - Paid orders cannot be cancelled by the customer (contact support)
    - Returns 403 if the order belongs to a different user
    - Returns 409 if the order is not in a cancellable state
    """
    return service.cancel_order(str(order_id), user_id=current_user.id)
