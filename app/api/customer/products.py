"""Customer — Products (read-only, active products only)."""
from uuid import UUID
from fastapi import APIRouter, Depends, Query
from app.dependencies.auth import get_current_user
from app.schemas.product import ProductListResponse, ProductResponse
from app.schemas.user import CurrentUser
from app.services.product_service import ProductService

router = APIRouter(prefix="/products", tags=["Customer — Products"])


@router.get("", response_model=ProductListResponse)
def list_products(
    page:             int        = Query(default=1, ge=1),
    page_size:        int        = Query(default=20, ge=1, le=100),
    search:           str | None = Query(default=None, max_length=100),
    category_id:      UUID | None = Query(default=None),
    in_stock_only:    bool       = Query(default=False),
    _: CurrentUser = Depends(get_current_user),
    service: ProductService = Depends(ProductService),
):
    return service.list_products(
        page=page, page_size=page_size, search=search,
        category_id=str(category_id) if category_id else None,
        in_stock_only=in_stock_only,
        include_inactive=False,   # customers never see inactive products
    )


@router.get("/{product_id}", response_model=ProductResponse)
def get_product(
    product_id: UUID,
    _: CurrentUser = Depends(get_current_user),
    service: ProductService = Depends(ProductService),
):
    return service.get_product(product_id)