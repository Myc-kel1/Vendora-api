"""
Product Repository — all DB operations for the products table.
Uses service role client (bypasses RLS) because access control
is enforced at the FastAPI dependency layer.
"""
from uuid import UUID
from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.core.supabase import get_supabase_admin_client

logger = get_logger(__name__)
TABLE  = "products"


class ProductRepository:
    def __init__(self):
        self.db = get_supabase_admin_client()

    def get_all(self, page=1, page_size=20, category_id=None,
                in_stock_only=False, search=None, include_inactive=False):
        offset = (page - 1) * page_size
        cq = self.db.table(TABLE).select("id", count="exact")
        dq = self.db.table(TABLE).select("*")
        if not include_inactive:
            cq = cq.eq("is_active", True)
            dq = dq.eq("is_active", True)
        if category_id:
            cq = cq.eq("category_id", category_id)
            dq = dq.eq("category_id", category_id)
        if in_stock_only:
            cq = cq.gt("stock", 0)
            dq = dq.gt("stock", 0)
        if search:
            cq = cq.ilike("name", f"%{search}%")
            dq = dq.ilike("name", f"%{search}%")
        total = (cq.execute().count or 0)
        items = dq.range(offset, offset + page_size - 1).execute().data or []
        return items, total

    def get_by_id(self, product_id: UUID) -> dict:
        res = self.db.table(TABLE).select("*").eq("id", str(product_id)).single().execute()
        if not res.data:
            raise NotFoundError(f"Product {product_id} not found")
        return res.data

    def get_many_by_ids(self, ids: list[str]) -> list[dict]:
        return self.db.table(TABLE).select("*").in_("id", ids).execute().data or []

    def create(self, data: dict) -> dict:
        res = self.db.table(TABLE).insert(data).execute()
        logger.info("product_created", product_id=res.data[0]["id"])
        return res.data[0]

    def update(self, product_id: UUID, data: dict) -> dict:
        res = self.db.table(TABLE).update(data).eq("id", str(product_id)).execute()
        if not res.data:
            raise NotFoundError(f"Product {product_id} not found")
        return res.data[0]

    def soft_delete(self, product_id: UUID) -> None:
        """Set is_active=False. Never hard-delete — order history references products."""
        self.db.table(TABLE).update({"is_active": False}).eq("id", str(product_id)).execute()
        logger.info("product_deactivated", product_id=str(product_id))

    def decrement_stock(self, product_id: str, quantity: int) -> None:
        """Atomic stock deduction via SQL RPC. Raises on insufficient stock."""
        self.db.rpc("decrement_stock", {
            "p_product_id": product_id,
            "p_quantity":   quantity,
        }).execute()