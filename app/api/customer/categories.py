"""
Customer — Categories Endpoints (Read-Only).

Customers can browse categories to:
  - Populate filter dropdowns on the product listing page
  - Navigate to a specific category's products

Write operations (create / update / delete) are admin-only.
All routes require a valid JWT (get_current_user dependency).
"""
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
    """
    List all product categories in alphabetical order.

    Use the returned category IDs with the product listing endpoint:
      GET /products?category_id=<uuid>

    Returns 401 if unauthenticated.
    """
    return service.list_categories()


@router.get("/{category_id}", response_model=CategoryResponse)
def get_category(
    category_id: UUID,
    _: CurrentUser = Depends(get_current_user),
    service: CategoryService = Depends(CategoryService),
):
    """
    Get a single category by ID.

    Returns 404 if the category does not exist.
    Returns 401 if unauthenticated.
    """
    return service.get_category(category_id)
