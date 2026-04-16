"""
Order Repository.

Handles all DB operations for orders and order_items tables.
"""
from app.core.exceptions import NotFoundError
from app.core.supabase import get_supabase_admin_client
from app.core.logging import get_logger

logger = get_logger(__name__)

ORDER_TABLE = "orders"
ITEM_TABLE = "order_items"


class OrderRepository:
    def __init__(self):
        self.db = get_supabase_admin_client()

    def create_order(self, user_id: str, total_amount: float) -> dict:
        """Insert a new order with 'pending' status."""
        data = {
            "user_id": user_id,
            "status": "pending",
            "total_amount": total_amount,
        }
        res = self.db.table(ORDER_TABLE).insert(data).execute()
        order = res.data[0]
        logger.info("order_created", order_id=order["id"], user_id=user_id)
        return order

    def insert_order_items(self, items: list[dict]) -> list[dict]:
        """Bulk insert order items for efficiency."""
        res = self.db.table(ITEM_TABLE).insert(items).execute()
        return res.data

    def get_order_by_id(self, order_id: str) -> dict:
        """Fetch a single order with items. Raises NotFoundError if missing."""
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

    def get_orders_by_user(self, user_id: str, page: int = 1, page_size: int = 20) -> tuple[list[dict], int]:
        """Fetch paginated orders for a specific user, newest first."""
        offset = (page - 1) * page_size

        count_res = (
            self.db.table(ORDER_TABLE)
            .select("id", count="exact")
            .eq("user_id", user_id)
            .execute()
        )
        total = count_res.count or 0

        res = (
            self.db.table(ORDER_TABLE)
            .select("*, order_items(*, products(id, name))")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .range(offset, offset + page_size - 1)
            .execute()
        )
        return res.data, total

    def get_all_orders(
        self,
        page: int = 1,
        page_size: int = 20,
        status_filter: str | None = None,
        user_id_filter: str | None = None,
    ) -> tuple[list[dict], int]:
        """Admin: fetch all orders paginated, newest first. Supports optional filters."""
        offset = (page - 1) * page_size

        # Build base query — apply filters to both count and data queries
        count_query = self.db.table(ORDER_TABLE).select("id", count="exact")
        data_query = (
            self.db.table(ORDER_TABLE)
            .select("*, order_items(*, products(id, name))")
            .order("created_at", desc=True)
        )

        if status_filter:
            count_query = count_query.eq("status", status_filter)
            data_query = data_query.eq("status", status_filter)

        if user_id_filter:
            count_query = count_query.eq("user_id", user_id_filter)
            data_query = data_query.eq("user_id", user_id_filter)

        count_res = count_query.execute()
        total = count_res.count or 0

        res = data_query.range(offset, offset + page_size - 1).execute()
        return res.data, total

    def update_order_status(self, order_id: str, status: str) -> dict:
        """Update order status. Used by admin and payment webhook."""
        res = (
            self.db.table(ORDER_TABLE)
            .update({"status": status})
            .eq("id", order_id)
            .execute()
        )
        if not res.data:
            raise NotFoundError(f"Order {order_id} not found")
        logger.info("order_status_updated", order_id=order_id, status=status)
        return res.data[0]

    def get_pending_order_for_user_cart(self, user_id: str, cart_id: str) -> dict | None:
        """
        Idempotency check: has this user already placed a pending order
        for the current cart contents? Used to prevent duplicate orders.
        """
        res = (
            self.db.table(ORDER_TABLE)
            .select("*")
            .eq("user_id", user_id)
            .eq("status", "pending")
            .eq("cart_id", cart_id)
            .limit(1)
            .execute()
        )
        return res.data[0] if res.data else None

    def get_order_by_payment_reference(self, reference: str) -> dict | None:
        """Look up order by Paystack payment reference (used in webhook)."""
        res = (
            self.db.table(ORDER_TABLE)
            .select("*")
            .eq("payment_reference", reference)
            .limit(1)
            .execute()
        )
        return res.data[0] if res.data else None

    def set_payment_reference(self, order_id: str, reference: str) -> dict:
        """Store the Paystack reference against the order for webhook lookup."""
        res = (
            self.db.table(ORDER_TABLE)
            .update({"payment_reference": reference})
            .eq("id", order_id)
            .execute()
        )
        return res.data[0]
