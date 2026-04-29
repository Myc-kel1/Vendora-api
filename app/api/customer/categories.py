"""Customer — Categories (read-only)."""
from uuid import UUID
from fastapi import APIRouter, Depends
from app.dependencies.auth import get_current_user
from app.schemas.product import CategoryResponse
from app.schemas.user import CurrentUser
from app.services.category_service import CategoryService

router = APIRouter(prefix="/categories", tags=["Customer — Categories"])


@router.get("", response_model=list[CategoryResponse])
def list_categories(
    _: CurrentUser = Depends(get_current_user),
    service: CategoryService = Depends(CategoryService),
):
    return service.list_categories()


@router.get("/{category_id}", response_model=CategoryResponse)
def get_category(
    category_id: UUID,
    _: CurrentUser = Depends(get_current_user),
    service: CategoryService = Depends(CategoryService),
):
    return service.get_category(category_id)