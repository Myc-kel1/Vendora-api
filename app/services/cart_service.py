"""
Cart Service.

Business logic for cart operations.

Key rules enforced here:
- Stock is validated before adding an item
- Duplicate items are merged (quantity incremented), not inserted again
- Quantity cannot be zero or negative (enforced at schema level, asserted here)
- Cart is persistent and tied to user_id
"""
from decimal import Decimal
from uuid import UUID

from app.core.exceptions import NotFoundError, StockError, ValidationError
from app.core.logging import get_logger
from app.repositories.cart_repository import CartRepository
from app.repositories.product_repository import ProductRepository
from app.schemas.cart import CartItemAdd, CartItemResponse, CartResponse

logger = get_logger(__name__)


class CartService:
    def __init__(self):
        self.cart_repo = CartRepository()
        self.product_repo = ProductRepository()

    def get_cart(self, user_id: str) -> CartResponse:
        """Fetch or create cart for user, returning full cart with item details."""
        raw = self.cart_repo.get_cart_with_items(user_id)
        return self._build_cart_response(raw)

    MAX_CART_ITEMS = 20  # Prevent abuse — no cart should have >20 distinct products

    def add_item(self, user_id: str, payload: CartItemAdd) -> CartResponse:
        """
        Add a product to the cart.

        Logic:
        1. Validate the product exists and has enough stock
        2. Get or create user's cart
        3. Enforce max cart items limit (20 distinct products)
        4. If product already in cart → merge (increment quantity)
        5. If new → insert item
        6. Return updated cart
        """
        product_id = str(payload.product_id)

        # 1. Validate product and stock
        product = self.product_repo.get_by_id(UUID(product_id))
        if product["stock"] < payload.quantity:
            raise StockError(
                f"Only {product['stock']} units of '{product['name']}' available"
            )

        # 2. Get or create cart
        cart = self.cart_repo.get_or_create_cart(user_id)
        cart_id = cart["id"]

        # 3. Enforce max cart items limit
        existing = self.cart_repo.get_item(cart_id, product_id)
        if not existing:
            # Only count when adding a NEW distinct product
            current_count = self.cart_repo.count_items(cart_id)
            if current_count >= self.MAX_CART_ITEMS:
                raise ValidationError(
                    f"Cart is full — maximum {self.MAX_CART_ITEMS} distinct products allowed. "
                    "Remove an item before adding a new one."
                )

        # 4. Merge or insert
        if existing:
            new_quantity = existing["quantity"] + payload.quantity
            # Re-validate merged quantity against stock
            if product["stock"] < new_quantity:
                raise StockError(
                    f"Cannot add {payload.quantity} more — only {product['stock']} total in stock"
                )
            self.cart_repo.update_item_quantity(existing["id"], new_quantity)
            logger.info("cart_item_merged", product_id=product_id, new_quantity=new_quantity)
        else:
            # New item
            self.cart_repo.add_item(cart_id, product_id, payload.quantity)
            logger.info("cart_item_added", product_id=product_id, quantity=payload.quantity)

        # 5. Return fresh cart
        return self.get_cart(user_id)

    def update_item(self, user_id: str, item_id: str, quantity: int) -> CartResponse:
        """
        Set the absolute quantity of a cart item.

        - Validates the new quantity against current stock
        - The item must belong to the user's cart (scoped by cart_id)
        """
        cart = self.cart_repo.get_or_create_cart(user_id)
        cart_id = cart["id"]

        # Verify item belongs to this cart
        item = self.cart_repo.get_item_by_id(item_id, cart_id)
        if not item:
            from app.core.exceptions import NotFoundError
            raise NotFoundError("Cart item not found")

        # Validate new quantity against stock
        product = self.product_repo.get_by_id(UUID(item["product_id"]))
        if product["stock"] < quantity:
            raise StockError(
                f"Only {product['stock']} units of '{product['name']}' available"
            )

        self.cart_repo.update_item_quantity(item_id, quantity)
        logger.info("cart_item_updated", item_id=item_id, quantity=quantity)
        return self.get_cart(user_id)

    def remove_item(self, user_id: str, item_id: str) -> CartResponse:
        """
        Remove a specific item from the cart.
        Scoped to the user's cart to prevent cross-user deletions.
        """
        cart = self.cart_repo.get_or_create_cart(user_id)
        self.cart_repo.remove_item(item_id, cart["id"])
        return self.get_cart(user_id)

    # ─── Internal Helpers ─────────────────────────────────────────────────────

    def _build_cart_response(self, raw: dict) -> CartResponse:
        """
        Transform raw Supabase nested response into CartResponse schema.
        Calculates subtotals and cart total here.
        """
        raw_items = raw.get("cart_items", [])
        items = []
        total = Decimal("0")

        for raw_item in raw_items:
            product = raw_item.get("products", {})
            price = Decimal(str(product.get("price", 0)))
            quantity = raw_item["quantity"]
            subtotal = price * quantity
            total += subtotal

            items.append(
                CartItemResponse(
                    id=raw_item["id"],
                    product_id=raw_item["product_id"],
                    product_name=product.get("name", ""),
                    product_price=price,
                    quantity=quantity,
                    subtotal=subtotal,
                )
            )

        return CartResponse(
            id=raw["id"],
            user_id=raw["user_id"],
            items=items,
            total=total,
        )
