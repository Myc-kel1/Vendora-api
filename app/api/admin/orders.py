from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.dependencies.auth import get_current_admin
from app.schemas.order import OrderListResponse, OrderResponse, OrderStatusUpdate
from app.schemas.user import CurrentUser
from app.services.order_service import OrderService

router = APIRouter(prefix="/admin/orders", tags=["Admin — Orders"])

# All valid order statuses as a type alias for Query validation
OrderStatusFilter = Literal["pending", "paid", "failed", "cancelled"]


@router.get("", response_model=OrderListResponse)
def list_all_orders(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: OrderStatusFilter | None = Query(default=None, description="Filter by order status"),
    user_id: str | None = Query(default=None, description="Filter by customer user UUID"),
    _: CurrentUser = Depends(get_current_admin),
    service: OrderService = Depends(OrderService),
):
    """
    Admin: view all orders across all customers.

    Supports optional filtering:
    - ?status=pending|paid|failed|cancelled
    - ?user_id=<uuid>  (view all orders for a specific customer)
    - Both filters can be combined
    """
    return service.get_all_orders(
        page=page,
        page_size=page_size,
        status_filter=status,
        user_id_filter=user_id,
    )


@router.get("/{order_id}", response_model=OrderResponse)
def get_order(
    order_id: UUID,
    _: CurrentUser = Depends(get_current_admin),
    service: OrderService = Depends(OrderService),
):
    """
    Admin: fetch full details of a single order by ID.
    Returns 404 if the order does not exist.
    """
    return service.get_order(str(order_id))


@router.put("/{order_id}/status", response_model=OrderResponse)
def update_order_status(
    order_id: UUID,
    payload: OrderStatusUpdate,
    _: CurrentUser = Depends(get_current_admin),
    service: OrderService = Depends(OrderService),
):
    """
    Admin: update an order's status.

    State machine rules — only valid transitions allowed:
    - pending  → paid | failed | cancelled
    - paid     → cancelled
    - failed   → pending
    - cancelled → (terminal — no transitions)
    """
    return service.update_order_status(str(order_id), payload.status)
