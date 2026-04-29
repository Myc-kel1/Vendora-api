"""Admin — Orders (global view + status update)."""
from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Depends, Query
from app.dependencies.auth import get_current_admin
from app.schemas.order import OrderListResponse, OrderResponse, OrderStatusUpdate
from app.schemas.user import CurrentUser
from app.services.order_service import OrderService

router = APIRouter(prefix="/admin/orders", tags=["Admin — Orders"])
OrderStatusFilter = Literal["pending", "paid", "failed", "cancelled"]


@router.get("", response_model=OrderListResponse)
def list_all_orders(
    page:           int                    = Query(default=1, ge=1),
    page_size:      int                    = Query(default=20, ge=1, le=100),
    status:         OrderStatusFilter | None = Query(default=None),
    user_id:        str | None             = Query(default=None),
    _: CurrentUser = Depends(get_current_admin),
    service: OrderService = Depends(OrderService),
):
    return service.get_all_orders(page=page, page_size=page_size, status_filter=status, user_id_filter=user_id)


@router.get("/{order_id}", response_model=OrderResponse)
def get_order(order_id: UUID, _: CurrentUser = Depends(get_current_admin), service: OrderService = Depends(OrderService)):
    return service.get_order(str(order_id))


@router.put("/{order_id}/status", response_model=OrderResponse)
def update_order_status(order_id: UUID, payload: OrderStatusUpdate, _: CurrentUser = Depends(get_current_admin), service: OrderService = Depends(OrderService)):
    return service.update_order_status(str(order_id), payload.status)