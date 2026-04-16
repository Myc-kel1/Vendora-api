"""
Cart Repository.

Handles all DB operations for carts and cart_items tables.
"""
from uuid import UUID

from app.core.exceptions import NotFoundError
from app.core.supabase import get_supabase_admin_client
from app.core.logging import get_logger

logger = get_logger(__name__)

CART_TABLE = "carts"
ITEM_TABLE = "cart_items"


class CartRepository:
    def __init__(self):
        self.db = get_supabase_admin_client()

    # ─── Cart ─────────────────────────────────────────────────────────────────

    def get_or_create_cart(self, user_id: str) -> dict:
        """
        Fetch existing cart for user, or create one if it doesn't exist.
        Each user has exactly one persistent cart.
        """
        res = (
            self.db.table(CART_TABLE)
            .select("*")
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        if res.data:
            return res.data[0]

        # Create new cart
        new_cart = self.db.table(CART_TABLE).insert({"user_id": user_id}).execute()
        logger.info("cart_created", user_id=user_id)
        return new_cart.data[0]

    def get_cart_with_items(self, user_id: str) -> dict:
        """
        Fetch cart + all items with product details in one query.
        Avoids N+1 by using Supabase's nested select syntax.
        """
        res = (
            self.db.table(CART_TABLE)
            .select(
                "*, cart_items(*, products(id, name, price, stock))"
            )
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        if not res.data:
            # Auto-create cart on first view
            cart = self.get_or_create_cart(user_id)
            cart["cart_items"] = []
            return cart
        return res.data[0]

    # ─── Cart Items ───────────────────────────────────────────────────────────

    def count_items(self, cart_id: str) -> int:
        """Return the number of distinct product lines in the cart."""
        res = (
            self.db.table(ITEM_TABLE)
            .select("id", count="exact")
            .eq("cart_id", cart_id)
            .execute()
        )
        return res.count or 0


    def get_item_by_id(self, item_id: str, cart_id: str) -> dict | None:
        """Fetch a specific cart item — scoped to cart_id for security."""
        res = (
            self.db.table(ITEM_TABLE)
            .select("*")
            .eq("id", item_id)
            .eq("cart_id", cart_id)
            .limit(1)
            .execute()
        )
        return res.data[0] if res.data else None

    def get_item(self, cart_id: str, product_id: str) -> dict | None:
        """Find an existing cart item for a product (for merge logic)."""
        res = (
            self.db.table(ITEM_TABLE)
            .select("*")
            .eq("cart_id", cart_id)
            .eq("product_id", product_id)
            .limit(1)
            .execute()
        )
        return res.data[0] if res.data else None

    def add_item(self, cart_id: str, product_id: str, quantity: int) -> dict:
        """Insert a new cart item."""
        data = {
            "cart_id": cart_id,
            "product_id": product_id,
            "quantity": quantity,
        }
        res = self.db.table(ITEM_TABLE).insert(data).execute()
        return res.data[0]

    def update_item_quantity(self, item_id: str, quantity: int) -> dict:
        """Update quantity of an existing cart item."""
        res = (
            self.db.table(ITEM_TABLE)
            .update({"quantity": quantity})
            .eq("id", item_id)
            .execute()
        )
        return res.data[0]

    def remove_item(self, item_id: str, cart_id: str) -> None:
        """
        Delete a cart item. Requires cart_id to scope the delete
        and prevent users from deleting other users' items.
        """
        self.db.table(ITEM_TABLE).delete().eq("id", item_id).eq("cart_id", cart_id).execute()
        logger.info("cart_item_removed", item_id=item_id)

    def clear_cart(self, cart_id: str) -> None:
        """Remove all items from a cart (called after order is placed)."""
        self.db.table(ITEM_TABLE).delete().eq("cart_id", cart_id).execute()
        logger.info("cart_cleared", cart_id=cart_id)
