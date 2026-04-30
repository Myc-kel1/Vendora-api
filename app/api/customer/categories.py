"""Customer — Categories (public, read-only)."""
from uuid import UUID
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from app.dependencies.auth import get_current_user_optional
from app.schemas.product import CategoryResponse
from app.schemas.user import CurrentUser
from app.services.category_service import CategoryService

router = APIRouter(prefix="/categories", tags=["Customer — Categories"])


@router.get("", response_model=list[CategoryResponse])
def list_categories(
    current_user: CurrentUser | None = Depends(get_current_user_optional),
    service: CategoryService = Depends(CategoryService),
):
    """
    List all categories (public endpoint).
    No authentication required.

    Cache-Control: Set to allow browsers and CDNs to cache this public data.
    """
    categories = service.list_categories()
    # Return JSONResponse to add caching headers for public data
    return JSONResponse(
        content=[cat.model_dump() if hasattr(cat, 'model_dump') else cat for cat in categories],
        headers={
            "Cache-Control": "public, max-age=3600",  # Cache for 1 hour
            "X-User-Id": current_user.id if current_user else "anonymous",
        }
    )


@router.get("/{category_id}", response_model=CategoryResponse)
def get_category(
    category_id: UUID,
    current_user: CurrentUser | None = Depends(get_current_user_optional),
    service: CategoryService = Depends(CategoryService),
):
    """
    Get a single category by ID (public endpoint).
    No authentication required.

    Cache-Control: Set to allow browsers and CDNs to cache this public data.
    """
    category = service.get_category(category_id)
    return JSONResponse(
        content=category.model_dump() if hasattr(category, 'model_dump') else category,
        headers={
            "Cache-Control": "public, max-age=3600",  # Cache for 1 hour
            "X-User-Id": current_user.id if current_user else "anonymous",
        }
    )