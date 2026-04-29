"""Admin — Categories CRUD."""
from uuid import UUID
from fastapi import APIRouter, Depends
from app.dependencies.auth import get_current_admin
from app.schemas.product import CategoryCreate, CategoryResponse, CategoryUpdate
from app.schemas.user import CurrentUser
from app.services.category_service import CategoryService

router = APIRouter(prefix="/admin/categories", tags=["Admin — Categories"])


@router.get("", response_model=list[CategoryResponse])
def list_categories(_: CurrentUser = Depends(get_current_admin), service: CategoryService = Depends(CategoryService)):
    return service.list_categories()


@router.post("", response_model=CategoryResponse, status_code=201)
def create_category(payload: CategoryCreate, _: CurrentUser = Depends(get_current_admin), service: CategoryService = Depends(CategoryService)):
    return service.create_category(payload)


@router.get("/{category_id}", response_model=CategoryResponse)
def get_category(category_id: UUID, _: CurrentUser = Depends(get_current_admin), service: CategoryService = Depends(CategoryService)):
    return service.get_category(category_id)


@router.patch("/{category_id}", response_model=CategoryResponse)
def update_category(category_id: UUID, payload: CategoryUpdate, _: CurrentUser = Depends(get_current_admin), service: CategoryService = Depends(CategoryService)):
    return service.update_category(category_id, payload)


@router.delete("/{category_id}", status_code=204)
def delete_category(category_id: UUID, _: CurrentUser = Depends(get_current_admin), service: CategoryService = Depends(CategoryService)):
    service.delete_category(category_id)