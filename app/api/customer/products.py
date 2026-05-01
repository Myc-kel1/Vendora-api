from uuid import UUID
from fastapi import APIRouter, Depends, Query, Response
from app.dependencies.auth import get_current_user_optional
from app.schemas.product import ProductListResponse, ProductResponse
from app.schemas.user import CurrentUser
from app.services.product_service import ProductService
from fastapi.encoders import jsonable_encoder
from decimal import Decimal

router = APIRouter(prefix="/products", tags=["Customer — Products"])


def safe(data):
    return jsonable_encoder(data, custom_encoder={Decimal: float})


@router.get("", response_model=ProductListResponse)
def list_products(
    response: Response,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: str | None = Query(default=None),
    category_id: UUID | None = Query(default=None),
    in_stock_only: bool = Query(default=False),
    current_user: CurrentUser | None = Depends(get_current_user_optional),
    service: ProductService = Depends(ProductService),
):
    result = service.list_products(
        page=page,
        page_size=page_size,
        search=search,
        category_id=str(category_id) if category_id else None,
        in_stock_only=in_stock_only,
        include_inactive=False,
    )

    response.headers["Cache-Control"] = "public, max-age=300"
    response.headers["X-User-Id"] = str(current_user.id) if current_user else "anonymous"

    return safe(result)


@router.get("/{product_id}", response_model=ProductResponse)
def get_product(
    product_id: UUID,
    response: Response,
    current_user: CurrentUser | None = Depends(get_current_user_optional),
    service: ProductService = Depends(ProductService),
):
    product = service.get_product(product_id)

    response.headers["Cache-Control"] = "public, max-age=3600"
    response.headers["X-User-Id"] = str(current_user.id) if current_user else "anonymous"

    return safe(product)