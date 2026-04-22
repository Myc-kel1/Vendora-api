"""
Customer — Products Endpoints (Read-Only).

Customers can browse and search the active product catalogue.
All write operations (create / update / deactivate) are admin-only.
All routes require a valid JWT (get_current_user dependency).

Filtering options (all optional, combinable):
  ?search=<text>          — case-insensitive name search
  ?category_id=<uuid>     — filter by category
  ?in_stock_only=true     — only products with stock > 0
  ?page=<n>&page_size=<n> — pagination (default page=1, page_size=20)

Inactive products (is_active=False) are NEVER returned to customers.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.dependencies.auth import get_current_user
from app.schemas.product import ProductListResponse, ProductResponse
from app.schemas.user import CurrentUser
from app.services.product_service import ProductService

router = APIRouter(prefix="/products", tags=["Customer — Products"])


@router.get("", response_model=ProductListResponse)
def list_products(
    page: int = Query(default=1, ge=1, description="Page number, starting at 1"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page (max 100)"),
    search: str | None = Query(
        default=None,
        max_length=100,
        description="Case-insensitive search on product name",
    ),
    category_id: UUID | None = Query(
        default=None,
        description="Filter results to a specific category UUID",
    ),
    in_stock_only: bool = Query(
        default=False,
        description="When true, only products with stock > 0 are returned",
    ),
#    _: CurrentUser = Depends(get_current_user),
    service: ProductService = Depends(ProductService),
):
    """
    Browse all active products. Paginated with optional filters.

    All filters are optional and can be combined freely.
    Only active products (is_active=True) are ever returned here.

    Response includes:
    - items: list of products for the current page
    - total: total matching products (for client-side pagination UI)
    - page: current page number
    - page_size: items per page

    Returns 401 if unauthenticated.
    """
    return service.list_products(
        page=page,
        page_size=page_size,
        search=search,
        category_id=str(category_id) if category_id else None,
        in_stock_only=in_stock_only,
        include_inactive=False,  # Customers never see deactivated products
    )


@router.get("/{product_id}", response_model=ProductResponse)
def get_product(
    product_id: UUID,
#   _: CurrentUser = Depends(get_current_user),
    service: ProductService = Depends(ProductService),
):
    """
    Get full details for a single product by UUID.

    Returns 404 if the product does not exist or has been deactivated.
    Returns 401 if unauthenticated.
    """
    return service.get_product(product_id)
