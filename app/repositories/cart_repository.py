"""Cart Repository."""
from app.core.supabase import get_supabase_admin_client

CART_TABLE = "carts"
ITEM_TABLE = "cart_items"


class CartRepository:
    def __init__(self):
        self.db = get_supabase_admin_client()

    def get_or_create_cart(self, user_id: str) -> dict:
        res = self.db.table(CART_TABLE).select("*").eq("user_id", user_id).single().execute()
        if res.data:
            return res.data
        return self.db.table(CART_TABLE).insert({"user_id": user_id}).execute().data[0]

    def get_cart_with_items(self, user_id: str) -> dict:
        """Fetch cart with nested items + product info in one query."""
        cart = self.get_or_create_cart(user_id)
        items = (
            self.db.table(ITEM_TABLE)
            .select("*, products(id, name, price, stock, image_url)")
            .eq("cart_id", cart["id"])
            .execute()
            .data or []
        )
        cart["cart_items"] = items
        return cart

    def get_item(self, cart_id: str, product_id: str) -> dict | None:
        res = (
            self.db.table(ITEM_TABLE)
            .select("*")
            .eq("cart_id", cart_id)
            .eq("product_id", product_id)
            .limit(1)
            .execute()
        )
        return res.data[0] if res.data else None

    def get_item_by_id(self, item_id: str, cart_id: str) -> dict | None:
        res = (
            self.db.table(ITEM_TABLE)
            .select("*")
            .eq("id", item_id)
            .eq("cart_id", cart_id)
            .limit(1)
            .execute()
        )
        return res.data[0] if res.data else None

    def count_items(self, cart_id: str) -> int:
        res = self.db.table(ITEM_TABLE).select("id", count="exact").eq("cart_id", cart_id).execute()
        return res.count or 0

    def add_item(self, cart_id: str, product_id: str, quantity: int) -> dict:
        return self.db.table(ITEM_TABLE).insert({
            "cart_id": cart_id, "product_id": product_id, "quantity": quantity
        }).execute().data[0]

    def update_item_quantity(self, item_id: str, quantity: int) -> dict:
        return self.db.table(ITEM_TABLE).update({"quantity": quantity}).eq("id", item_id).execute().data[0]

    def remove_item(self, item_id: str, cart_id: str) -> None:
        self.db.table(ITEM_TABLE).delete().eq("id", item_id).eq("cart_id", cart_id).execute()

    def clear_cart(self, cart_id: str) -> None:
        self.db.table(ITEM_TABLE).delete().eq("cart_id", cart_id).execute()