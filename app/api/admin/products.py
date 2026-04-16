from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.dependencies.auth import get_current_admin
from app.schemas.product import (
    CategoryResponse,
    ProductCreate,
    ProductListResponse,
    ProductResponse,
    ProductUpdate,
)
from app.schemas.user import CurrentUser
from app.services.product_service import ProductService

router = APIRouter(prefix="/admin/products", tags=["Admin — Products"])


@router.get("", response_model=ProductListResponse)
def list_products(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: str | None = Query(default=None, description="Search by product name"),
    category_id: UUID | None = Query(default=None, description="Filter by category"),
    in_stock_only: bool = Query(default=False),
    include_inactive: bool = Query(default=True, description="Include deactivated products"),
    _: CurrentUser = Depends(get_current_admin),
    service: ProductService = Depends(ProductService),
):
    """
    Admin: list all products with full filtering support.
    Includes inactive (soft-deleted) products by default.
    """
    return service.list_products(
        page=page,
        page_size=page_size,
        search=search,
        category_id=str(category_id) if category_id else None,
        in_stock_only=in_stock_only,
        include_inactive=include_inactive,
    )


@router.post("", response_model=ProductResponse, status_code=201)
def create_product(
    payload: ProductCreate,
    current_admin: CurrentUser = Depends(get_current_admin),
    service: ProductService = Depends(ProductService),
):
    """Admin: create a new product."""
    return service.create_product(payload, admin_id=current_admin.id)


@router.get("/{product_id}", response_model=ProductResponse)
def get_product(
    product_id: UUID,
    _: CurrentUser = Depends(get_current_admin),
    service: ProductService = Depends(ProductService),
):
    """Admin: get full product details including inactive ones."""
    return service.get_product(product_id)


@router.patch("/{product_id}", response_model=ProductResponse)
def update_product(
    product_id: UUID,
    payload: ProductUpdate,
    _: CurrentUser = Depends(get_current_admin),
    service: ProductService = Depends(ProductService),
):
    """
    Admin: partially update a product.
    Only send the fields you want to change — omitted fields are unchanged.
    Set is_active=false to soft-disable a product without deleting it.
    """
    return service.update_product(product_id, payload)


@router.patch("/{product_id}/stock", response_model=ProductResponse)
def update_stock(
    product_id: UUID,
    new_stock: int = Query(..., ge=0, description="New absolute stock level"),
    _: CurrentUser = Depends(get_current_admin),
    service: ProductService = Depends(ProductService),
):
    """
    Admin: update product stock level directly.
    Use this for inventory corrections (e.g. after a manual stocktake).
    For relative adjustments, use PATCH /admin/products/{id} with stock field.
    """
    return service.update_stock(product_id, new_stock)


@router.delete("/{product_id}", status_code=204)
def deactivate_product(
    product_id: UUID,
    _: CurrentUser = Depends(get_current_admin),
    service: ProductService = Depends(ProductService),
):
    """
    Admin: soft-delete (deactivate) a product.

    Sets is_active=False — the product is hidden from customers but the
    record is preserved because order history references it.
    Hard deletion is intentionally not supported.
    """
    service.delete_product(product_id)
