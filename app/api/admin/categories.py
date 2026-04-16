"""
Admin: Categories CRUD.
Full create/update/delete for category management.
"""
from uuid import UUID

from fastapi import APIRouter, Depends

from app.dependencies.auth import get_current_admin
from app.schemas.product import CategoryCreate, CategoryResponse, CategoryUpdate
from app.schemas.user import CurrentUser
from app.services.category_service import CategoryService

router = APIRouter(prefix="/admin/categories", tags=["Admin — Categories"])


@router.get("", response_model=list[CategoryResponse])
def list_categories(
    _: CurrentUser = Depends(get_current_admin),
    service: CategoryService = Depends(CategoryService),
):
    """Admin: list all categories."""
    return service.list_categories()


@router.post("", response_model=CategoryResponse, status_code=201)
def create_category(
    payload: CategoryCreate,
    _: CurrentUser = Depends(get_current_admin),
    service: CategoryService = Depends(CategoryService),
):
    """
    Admin: create a new product category.
    Returns 409 if a category with this name already exists.
    """
    return service.create_category(payload)


@router.get("/{category_id}", response_model=CategoryResponse)
def get_category(
    category_id: UUID,
    _: CurrentUser = Depends(get_current_admin),
    service: CategoryService = Depends(CategoryService),
):
    """Admin: get a single category by ID."""
    return service.get_category(category_id)


@router.patch("/{category_id}", response_model=CategoryResponse)
def update_category(
    category_id: UUID,
    payload: CategoryUpdate,
    _: CurrentUser = Depends(get_current_admin),
    service: CategoryService = Depends(CategoryService),
):
    """Admin: rename a category. Returns 409 if new name already exists."""
    return service.update_category(category_id, payload)


@router.delete("/{category_id}", status_code=204)
def delete_category(
    category_id: UUID,
    _: CurrentUser = Depends(get_current_admin),
    service: CategoryService = Depends(CategoryService),
):
    """
    Admin: delete a category.
    Products assigned to this category have their category_id set to NULL.
    Products are NOT deleted.
    """
    service.delete_category(category_id)
