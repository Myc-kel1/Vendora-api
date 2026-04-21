"""Product Service."""
from uuid import UUID
from app.repositories.product_repository import ProductRepository
from app.schemas.product import ProductCreate, ProductListResponse, ProductResponse, ProductUpdate


class ProductService:
    def __init__(self):
        self.repo = ProductRepository()

    def list_products(self, page=1, page_size=20, category_id=None,
                      in_stock_only=False, search=None, include_inactive=False):
        items, total = self.repo.get_all(
            page=page, page_size=page_size, category_id=category_id,
            in_stock_only=in_stock_only, search=search, include_inactive=include_inactive,
        )
        return ProductListResponse(items=items, total=total, page=page, page_size=page_size)

    def get_product(self, product_id: UUID) -> ProductResponse:
        return ProductResponse(**self.repo.get_by_id(product_id))

    def create_product(self, data: ProductCreate, admin_id: str) -> ProductResponse:
        payload = data.model_dump()
        payload["created_by"] = admin_id
        payload["is_active"]  = True
        payload["price"]      = float(payload["price"])
        if payload.get("category_id"):
            payload["category_id"] = str(payload["category_id"])
        return ProductResponse(**self.repo.create(payload))

    def update_product(self, product_id: UUID, data: ProductUpdate) -> ProductResponse:
        payload = data.model_dump(exclude_unset=True)
        if "price" in payload:
            payload["price"] = float(payload["price"])
        if "category_id" in payload and payload["category_id"]:
            payload["category_id"] = str(payload["category_id"])
        return ProductResponse(**self.repo.update(product_id, payload))

    def delete_product(self, product_id: UUID) -> None:
        self.repo.get_by_id(product_id)
        self.repo.soft_delete(product_id)

    def update_stock(self, product_id: UUID, new_stock: int) -> ProductResponse:
        return ProductResponse(**self.repo.update(product_id, {"stock": new_stock}))

    def set_image_url(self, product_id: UUID, image_url: str | None) -> ProductResponse:
        """Save (or clear) the product image URL after a storage upload."""
        return ProductResponse(**self.repo.update(product_id, {"image_url": image_url}))