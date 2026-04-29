"""Category Service."""
from uuid import UUID
from app.repositories.category_repository import CategoryRepository
from app.schemas.product import CategoryCreate, CategoryResponse, CategoryUpdate


class CategoryService:
    def __init__(self):
        self.repo = CategoryRepository()

    def list_categories(self) -> list[CategoryResponse]:
        return [CategoryResponse(**c) for c in self.repo.get_all()]

    def get_category(self, cat_id: UUID) -> CategoryResponse:
        return CategoryResponse(**self.repo.get_by_id(cat_id))

    def create_category(self, data: CategoryCreate) -> CategoryResponse:
        return CategoryResponse(**self.repo.create(data.name))

    def update_category(self, cat_id: UUID, data: CategoryUpdate) -> CategoryResponse:
        return CategoryResponse(**self.repo.update(cat_id, data.name))

    def delete_category(self, cat_id: UUID) -> None:
        self.repo.delete(cat_id)