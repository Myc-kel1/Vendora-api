"""Customer — Categories (public, read-only)."""
from uuid import UUID
from fastapi import APIRouter, Depends, Response
from app.dependencies.auth import get_current_user_optional
from app.schemas.product import CategoryResponse
from app.schemas.user import CurrentUser
from app.services.category_service import CategoryService

router = APIRouter(prefix="/categories", tags=["Customer — Categories"])


@router.get("", response_model=list[CategoryResponse])
def list_categories(
    response: Response,  # 👈 inject response
    current_user: CurrentUser | None = Depends(get_current_user_optional),
    service: CategoryService = Depends(CategoryService),
):
    categories = service.list_categories()

    # ✅ Set headers safely
    response.headers["Cache-Control"] = "public, max-age=3600"
    response.headers["X-User-Id"] = str(current_user.id) if current_user else "anonymous"

    return categories  # ✅ CRITICAL FIX


@router.get("/{category_id}", response_model=CategoryResponse)
def get_category(
    category_id: UUID,
    response: Response,  # 👈 inject response
    current_user: CurrentUser | None = Depends(get_current_user_optional),
    service: CategoryService = Depends(CategoryService),
):
    category = service.get_category(category_id)

    response.headers["Cache-Control"] = "public, max-age=3600"
    response.headers["X-User-Id"] = str(current_user.id) if current_user else "anonymous"

    return category  # ✅ CRITICAL FIX