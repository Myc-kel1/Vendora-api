"""
Product Repository.

All database operations for the products table.
Uses the admin Supabase client so RLS doesn't block backend reads,
but write operations are only called from admin-guarded service paths.
"""
from uuid import UUID

from app.core.exceptions import NotFoundError
from app.core.supabase import get_supabase_admin_client
from app.core.logging import get_logger

logger = get_logger(__name__)

TABLE = "products"


class ProductRepository:
    def __init__(self):
        self.db = get_supabase_admin_client()

    def get_all(
        self,
        page: int = 1,
        page_size: int = 20,
        category_id: str | None = None,
        in_stock_only: bool = False,
        search: str | None = None,
        include_inactive: bool = False,
    ) -> tuple[list[dict], int]:
        """Return paginated products with optional filters."""
        offset = (page - 1) * page_size

        count_q = self.db.table(TABLE).select("id", count="exact")
        data_q = self.db.table(TABLE).select("*")

        # Active-only by default (customers never see inactive products)
        if not include_inactive:
            count_q = count_q.eq("is_active", True)
            data_q = data_q.eq("is_active", True)

        if category_id:
            count_q = count_q.eq("category_id", category_id)
            data_q = data_q.eq("category_id", category_id)

        if in_stock_only:
            count_q = count_q.gt("stock", 0)
            data_q = data_q.gt("stock", 0)

        if search:
            # Supabase ilike for case-insensitive name search
            count_q = count_q.ilike("name", f"%{search}%")
            data_q = data_q.ilike("name", f"%{search}%")

        count_res = count_q.execute()
        total = count_res.count or 0

        res = data_q.range(offset, offset + page_size - 1).execute()
        return res.data, total

    def get_by_id(self, product_id: UUID) -> dict:
        """Fetch a single product by ID. Raises NotFoundError if missing."""
        res = (
            self.db.table(TABLE)
            .select("*")
            .eq("id", str(product_id))
            .single()
            .execute()
        )
        if not res.data:
            raise NotFoundError(f"Product {product_id} not found")
        return res.data

    def get_many_by_ids(self, product_ids: list[str]) -> list[dict]:
        """Fetch multiple products by IDs in one query (avoids N+1)."""
        res = (
            self.db.table(TABLE)
            .select("*")
            .in_("id", product_ids)
            .execute()
        )
        return res.data

    def create(self, data: dict) -> dict:
        """Insert a new product. Returns the created record."""
        res = self.db.table(TABLE).insert(data).execute()
        logger.info("product_created", product_id=res.data[0]["id"])
        return res.data[0]

    def update(self, product_id: UUID, data: dict) -> dict:
        """Partial update a product. Raises NotFoundError if missing."""
        res = (
            self.db.table(TABLE)
            .update(data)
            .eq("id", str(product_id))
            .execute()
        )
        if not res.data:
            raise NotFoundError(f"Product {product_id} not found")
        logger.info("product_updated", product_id=str(product_id))
        return res.data[0]

    def soft_delete(self, product_id: UUID) -> None:
        """
        Soft delete: set is_active=False.
        Never hard-delete products — order history references them.
        """
        self.db.table(TABLE).update({"is_active": False}).eq("id", str(product_id)).execute()
        logger.info("product_deactivated", product_id=str(product_id))

    def decrement_stock(self, product_id: str, quantity: int) -> dict:
        """
        Atomically decrement stock using Supabase RPC.
        The SQL function 'decrement_stock' checks for sufficient stock
        and raises an exception if stock would go negative.
        """
        res = self.db.rpc(
            "decrement_stock",
            {"p_product_id": product_id, "p_quantity": quantity},
        ).execute()
        return res.data

