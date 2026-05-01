from uuid import UUID
from fastapi import APIRouter, Depends, Response
from app.dependencies.auth import get_current_user_optional
from app.schemas.product import CategoryResponse
from app.schemas.user import CurrentUser
from app.services.category_service import CategoryService
from fastapi.encoders import jsonable_encoder
from decimal import Decimal

router = APIRouter(prefix="/categories", tags=["Customer — Categories"])


def safe(data):
    return jsonable_encoder(data, custom_encoder={Decimal: float})


@router.get("", response_model=list[CategoryResponse])
def list_categories(
    response: Response,
    current_user: CurrentUser | None = Depends(get_current_user_optional),
    service: CategoryService = Depends(CategoryService),
):
    categories = service.list_categories()

    response.headers["Cache-Control"] = "public, max-age=3600"
    response.headers["X-User-Id"] = str(current_user.id) if current_user else "anonymous"

    return safe(categories)


@router.get("/{category_id}", response_model=CategoryResponse)
def get_category(
    category_id: UUID,
    response: Response,
    current_user: CurrentUser | None = Depends(get_current_user_optional),
    service: CategoryService = Depends(CategoryService),
):
    category = service.get_category(category_id)

    response.headers["Cache-Control"] = "public, max-age=3600"
    response.headers["X-User-Id"] = str(current_user.id) if current_user else "anonymous"

    return safe(category)