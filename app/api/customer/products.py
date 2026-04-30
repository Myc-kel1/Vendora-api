"""Customer — Products (public, read-only, active products only)."""
from uuid import UUID
from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from app.dependencies.auth import get_current_user_optional
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
    current_user: CurrentUser | None = Depends(get_current_user_optional),
    service: ProductService = Depends(ProductService),
):
    """
    List products with optional filtering (public endpoint).
    No authentication required.

    Query parameters:
      - page: Page number (default: 1)
      - page_size: Items per page (default: 20, max: 100)
      - search: Search by name/description
      - category_id: Filter by category UUID
      - in_stock_only: Show only items in stock (default: False)

    Cache-Control: Varies by filters; dynamic responses bypass cache.
    """
    response = service.list_products(
        page=page, page_size=page_size, search=search,
        category_id=str(category_id) if category_id else None,
        in_stock_only=in_stock_only,
        include_inactive=False,   # customers never see inactive products
    )
    
    return JSONResponse(
        content=response.model_dump() if hasattr(response, 'model_dump') else response,
        headers={
            # Dynamic filters bypass cache; unfiltered lists can be cached
            "Cache-Control": "public, max-age=300" if not (search or in_stock_only) else "no-cache, must-revalidate",
            "X-User-Id": current_user.id if current_user else "anonymous",
        }
    )


@router.get("/{product_id}", response_model=ProductResponse)
def get_product(
    product_id: UUID,
    current_user: CurrentUser | None = Depends(get_current_user_optional),
    service: ProductService = Depends(ProductService),
):
    """
    Get a single product by ID (public endpoint).
    No authentication required.

    Cache-Control: Set to allow browsers and CDNs to cache this public data.
    """
    product = service.get_product(product_id)
    return JSONResponse(
        content=product.model_dump() if hasattr(product, 'model_dump') else product,
        headers={
            "Cache-Control": "public, max-age=3600",  # Cache for 1 hour
            "X-User-Id": current_user.id if current_user else "anonymous",
        }
    )