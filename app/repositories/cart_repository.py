"""Cart Repository - hardened against Supabase edge cases."""

from app.core.supabase import get_supabase_admin_client

CART_TABLE = "carts"
ITEM_TABLE = "cart_items"


class CartRepository:
    def __init__(self):
        self.db = get_supabase_admin_client()

    # -------------------------
    # CART
    # -------------------------
    def get_or_create_cart(self, user_id: str) -> dict:
        res = (
            self.db.table(CART_TABLE)
            .select("*")
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )

        data = getattr(res, "data", None)

        if data:
            return data[0]

        # create cart (NO select chaining here)
        create_res = (
            self.db.table(CART_TABLE)
            .insert({"user_id": user_id})
            .execute()
        )

        created = getattr(create_res, "data", None)

        if not created:
            raise RuntimeError("Cart creation failed")

        # 🔥 re-fetch safely (BEST PRACTICE FIX)
        fresh = (
            self.db.table(CART_TABLE)
            .select("*")
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )

        return fresh.data[0]
    # -------------------------
    # CART + ITEMS
    # -------------------------
    def get_cart_with_items(self, user_id: str) -> dict:
        cart = self.get_or_create_cart(user_id)

        res = (
            self.db.table(ITEM_TABLE)
            .select("*, products(id, name, price, stock, image_url)")
            .eq("cart_id", cart["id"])
            .execute()
        )

        items = getattr(res, "data", None) if res else [] or []

        cart["cart_items"] = items or []
        return cart

    # -------------------------
    # ITEMS
    # -------------------------
    def get_item(self, cart_id: str, product_id: str) -> dict | None:
        res = (
            self.db.table(ITEM_TABLE)
            .select("*")
            .eq("cart_id", cart_id)
            .eq("product_id", product_id)
            .limit(1)
            .execute()
        )

        data = getattr(res, "data", None) if res else None
        return data[0] if data else None

    def get_item_by_id(self, item_id: str, cart_id: str) -> dict | None:
        res = (
            self.db.table(ITEM_TABLE)
            .select("*")
            .eq("id", item_id)
            .eq("cart_id", cart_id)
            .limit(1)
            .execute()
        )

        data = getattr(res, "data", None) if res else None
        return data[0] if data else None

    def count_items(self, cart_id: str) -> int:
        res = (
            self.db.table(ITEM_TABLE)
            .select("id", count="exact")
            .eq("cart_id", cart_id)
            .execute()
        )

        return getattr(res, "count", 0) or 0

    # -------------------------
    # MUTATIONS
    # -------------------------
    def add_item(self, cart_id: str, product_id: str, quantity: int) -> dict:
        existing_item = self.get_item(cart_id, product_id)
        if existing_item:
            new_quantity = existing_item["quantity"] + quantity
            return self.update_item_quantity(existing_item["id"], new_quantity)
        else:
            self.db.table(ITEM_TABLE).insert({
                "cart_id": cart_id,
                "product_id": product_id,
                "quantity": quantity
            }).execute()
            # safest approach: re-query
            res = (
                self.db.table(ITEM_TABLE)
                .select("*")
                .eq("cart_id", cart_id)
                .eq("product_id", product_id)
                .limit(1)
                .execute()
            )
            return res.data[0]

    def update_item_quantity(self, item_id: str, quantity: int) -> dict:
        self.db.table(ITEM_TABLE).update({
            "quantity": quantity
        }).eq("id", item_id).execute()

        res = (
            self.db.table(ITEM_TABLE)
            .select("*")
            .eq("id", item_id)
            .limit(1)
            .execute()
        )

        return res.data[0]

    def remove_item(self, item_id: str, cart_id: str) -> None:
        self.db.table(ITEM_TABLE).delete().eq("id", item_id).eq("cart_id", cart_id).execute()

    def clear_cart(self, cart_id: str) -> None:
        self.db.table(ITEM_TABLE).delete().eq("cart_id", cart_id).execute()