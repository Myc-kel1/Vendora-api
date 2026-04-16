"""
Product Service.

Business logic for product operations.
Thin orchestration layer between routes and repository.
"""
from uuid import UUID

from app.repositories.product_repository import ProductRepository
from app.schemas.product import ProductCreate, ProductListResponse, ProductResponse, ProductUpdate


class ProductService:
    def __init__(self):
        self.repo = ProductRepository()

    def list_products(
        self,
        page: int = 1,
        page_size: int = 20,
        category_id: str | None = None,
        in_stock_only: bool = False,
        search: str | None = None,
        include_inactive: bool = False,  # admin only
    ) -> ProductListResponse:
        """Return paginated product listing with optional filters."""
        items, total = self.repo.get_all(
            page=page,
            page_size=page_size,
            category_id=category_id,
            in_stock_only=in_stock_only,
            search=search,
            include_inactive=include_inactive,
        )
        return ProductListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )

    def get_product(self, product_id: UUID) -> ProductResponse:
        """Fetch a single product by ID."""
        product = self.repo.get_by_id(product_id)
        return ProductResponse(**product)

    def create_product(self, data: ProductCreate, admin_id: str) -> ProductResponse:
        """
        Admin: create a new product.
        Injects the admin's user_id as created_by.
        """
        payload = data.model_dump()
        payload["created_by"] = admin_id
        payload["is_active"] = True
        payload["price"] = float(payload["price"])
        if payload.get("category_id"):
            payload["category_id"] = str(payload["category_id"])

        created = self.repo.create(payload)
        return ProductResponse(**created)

    def update_product(self, product_id: UUID, data: ProductUpdate) -> ProductResponse:
        """
        Admin: partial update of a product.
        Only provided fields are updated (exclude_unset=True).
        """
        payload = data.model_dump(exclude_unset=True)
        if "price" in payload:
            payload["price"] = float(payload["price"])
        if "category_id" in payload and payload["category_id"]:
            payload["category_id"] = str(payload["category_id"])

        updated = self.repo.update(product_id, payload)
        return ProductResponse(**updated)

    def delete_product(self, product_id: UUID) -> None:
        """
        Admin: soft-delete a product by setting is_active=False.
        Hard delete is intentionally avoided — order history references products.
        """
        self.repo.get_by_id(product_id)  # raises NotFoundError if missing
        self.repo.soft_delete(product_id)

    def update_stock(self, product_id: UUID, new_stock: int) -> ProductResponse:
        """Admin: dedicated inventory stock update."""
        updated = self.repo.update(product_id, {"stock": new_stock})
        return ProductResponse(**updated)
