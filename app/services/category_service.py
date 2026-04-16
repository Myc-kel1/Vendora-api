"""
Category Service.

Business logic for product category management.

Access rules:
  READ  — any authenticated user (customer or admin)
  WRITE — admin only (enforced at the route layer via get_current_admin)

This service is intentionally thin — categories are simple reference
data with no complex business rules beyond duplicate name prevention
(which is enforced in the repository layer).

Used by:
  Customer routes → GET /categories, GET /categories/{id}
  Admin routes    → GET, POST, PATCH, DELETE /admin/categories
"""
from uuid import UUID

from app.repositories.category_repository import CategoryRepository
from app.schemas.product import CategoryCreate, CategoryResponse, CategoryUpdate


class CategoryService:
    def __init__(self):
        self.repo = CategoryRepository()

    def list_categories(self) -> list[CategoryResponse]:
        """
        Return all categories in alphabetical order.

        Available to all authenticated users — used by the product
        listing page to populate filter dropdowns.
        """
        categories = self.repo.get_all()
        return [CategoryResponse(**c) for c in categories]

    def get_category(self, category_id: UUID) -> CategoryResponse:
        """
        Fetch a single category by UUID.

        Raises:
            NotFoundError (404): if the category does not exist.
        """
        category = self.repo.get_by_id(category_id)
        return CategoryResponse(**category)

    def create_category(self, data: CategoryCreate) -> CategoryResponse:
        """
        Admin: create a new product category.

        Raises:
            ConflictError (409): if a category with this name already exists.
                                 Category names are unique and case-sensitive.
        """
        category = self.repo.create(name=data.name)
        return CategoryResponse(**category)

    def update_category(self, category_id: UUID, data: CategoryUpdate) -> CategoryResponse:
        """
        Admin: rename an existing category.

        Raises:
            NotFoundError (404): if the category does not exist.
            ConflictError (409): if the new name is already taken by
                                 a different category.
        """
        category = self.repo.update(category_id, name=data.name)
        return CategoryResponse(**category)

    def delete_category(self, category_id: UUID) -> None:
        """
        Admin: delete a category.

        Products that were assigned to this category have their
        category_id set to NULL by the database FK constraint
        (ON DELETE SET NULL). The products themselves are NOT deleted.

        Raises:
            NotFoundError (404): if the category does not exist.
        """
        self.repo.delete(category_id)
