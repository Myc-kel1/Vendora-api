"""Order Repository."""
from app.core.exceptions import NotFoundError
from app.core.supabase import get_supabase_admin_client

ORDER_TABLE = "orders"
ITEM_TABLE  = "order_items"


class OrderRepository:
    def __init__(self):
        self.db = get_supabase_admin_client()

    def get_order_by_id(self, order_id: str) -> dict:
        res = (
            self.db.table(ORDER_TABLE)
            .select("*, order_items(*, products(id, name))")
            .eq("id", order_id)
            .single()
            .execute()
        )
        if not res.data:
            raise NotFoundError(f"Order {order_id} not found")
        return res.data

    def get_order_by_payment_reference(self, reference: str) -> dict | None:
        res = self.db.table(ORDER_TABLE).select("*").eq("payment_reference", reference).limit(1).execute()
        return res.data[0] if res.data else None

    def get_my_orders(self, user_id: str, page=1, page_size=20):
        offset = (page - 1) * page_size
        total = (self.db.table(ORDER_TABLE).select("id", count="exact").eq("user_id", user_id).execute().count or 0)
        items = (
            self.db.table(ORDER_TABLE)
            .select("*, order_items(*, products(id, name))")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .range(offset, offset + page_size - 1)
            .execute()
            .data or []
        )
        return items, total

    def get_all_orders(self, page=1, page_size=20, status_filter=None, user_id_filter=None):
        offset = (page - 1) * page_size
        cq = self.db.table(ORDER_TABLE).select("id", count="exact")
        dq = self.db.table(ORDER_TABLE).select("*, order_items(*, products(id, name))").order("created_at", desc=True)
        if status_filter:
            cq = cq.eq("status", status_filter)
            dq = dq.eq("status", status_filter)
        if user_id_filter:
            cq = cq.eq("user_id", user_id_filter)
            dq = dq.eq("user_id", user_id_filter)
        total = (cq.execute().count or 0)
        items = dq.range(offset, offset + page_size - 1).execute().data or []
        return items, total

    def create_order(self, user_id: str, total_amount: float, cart_id: str) -> dict:
        return self.db.table(ORDER_TABLE).insert({
            "user_id": user_id, "total_amount": total_amount,
            "status": "pending", "cart_id": cart_id,
        }).execute().data[0]

    def insert_order_items(self, order_id: str, items: list[dict]) -> None:
        rows = [{"order_id": order_id, **i} for i in items]
        self.db.table(ITEM_TABLE).insert(rows).execute()

    def update_order_status(self, order_id: str, status: str) -> None:
        self.db.table(ORDER_TABLE).update({"status": status}).eq("id", order_id).execute()

    def set_payment_reference(self, order_id: str, reference: str) -> None:
        self.db.table(ORDER_TABLE).update({"payment_reference": reference}).eq("id", order_id).execute()