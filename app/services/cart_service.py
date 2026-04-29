"""
Cart Service — business logic for cart operations.

Key rules enforced:
  - Stock validated before adding (and re-validated on merged qty)
  - Duplicate products merged (quantity incremented, not duplicated)
  - Max 20 distinct products per cart (abuse prevention)
  - Cart item removal scoped to user's cart_id (prevents cross-user delete)
"""
from decimal import Decimal
from uuid import UUID

from app.core.exceptions import NotFoundError, StockError, ValidationError
from app.core.logging import get_logger
from app.repositories.cart_repository import CartRepository
from app.repositories.product_repository import ProductRepository
from app.schemas.cart import CartItemAdd, CartItemUpdate, CartResponse, CartItemResponse

logger = get_logger(__name__)
MAX_CART_ITEMS = 20
MAX_ITEM_QUANTITY = 99

class CartService:
    def __init__(self):
        self.cart_repo    = CartRepository()
        self.product_repo = ProductRepository()

    def _build_response(self, user_id: str) -> CartResponse:
        raw  = self.cart_repo.get_cart_with_items(user_id)
        items = []
        for ci in raw.get("cart_items", []):
            prod = ci.get("products", {}) or {}
            price    = Decimal(str(prod.get("price", 0)))
            quantity = ci["quantity"]
            items.append(CartItemResponse(
                id=ci["id"], product_id=ci["product_id"],
                product_name=prod.get("name", ""),
                product_price=price,
                quantity=quantity,
                subtotal=price * quantity,
                image_url=prod.get("image_url"),
            ))
        return CartResponse(
            id=raw["id"], user_id=user_id,
            items=items,
            total=sum(i.subtotal for i in items),
        )

    def get_cart(self, user_id: str) -> CartResponse:
        return self._build_response(user_id)

def add_item(self, user_id: str, payload: CartItemAdd) -> CartResponse:
    """
    Add a product to the cart with full validation:
      1. Product must exist
      2. Requested quantity must be ≤ MAX_ITEM_QUANTITY
      3. Stock must cover the requested quantity
      4. Cart must not exceed MAX_CART_ITEMS distinct products
      5. Merged quantity must still be ≤ stock and ≤ MAX_ITEM_QUANTITY
    """
    product_id = str(payload.product_id)
    product    = self.product_repo.get_by_id(payload.product_id)

    if payload.quantity > MAX_ITEM_QUANTITY:
        raise ValidationError(f"Maximum quantity per item is {MAX_ITEM_QUANTITY}")

    cart    = self.cart_repo.get_or_create_cart(user_id)
    cart_id = cart["id"]
    existing = self.cart_repo.get_item(cart_id, product_id)

    if not existing:
        if self.cart_repo.count_items(cart_id) >= MAX_CART_ITEMS:
            raise ValidationError(
                f"Cart is full — maximum {MAX_CART_ITEMS} distinct products allowed. "
                "Remove an item before adding a new one."
            )
        if product["stock"] < payload.quantity:
            raise StockError(
                f"Only {product['stock']} unit(s) of '{product['name']}' available"
            )
        self.cart_repo.add_item(cart_id, product_id, payload.quantity)
    else:
        new_qty = existing["quantity"] + payload.quantity
        if new_qty > MAX_ITEM_QUANTITY:
            raise ValidationError(
                f"Maximum quantity per item is {MAX_ITEM_QUANTITY} "
                f"(you already have {existing['quantity']} in cart)"
            )
        if product["stock"] < new_qty:
            raise StockError(
                f"Only {product['stock']} unit(s) of '{product['name']}' available "
                f"(you already have {existing['quantity']} in cart)"
            )
        self.cart_repo.update_item_quantity(existing["id"], new_qty)

    logger.info("cart_item_added", user_id=user_id,
                product_id=product_id, quantity=payload.quantity)
    return self._build_response(user_id)

    def update_item(self, user_id: str, item_id: str, quantity: int) -> CartResponse:
        cart = self.cart_repo.get_or_create_cart(user_id)
        item = self.cart_repo.get_item_by_id(item_id, cart["id"])
        if not item:
            raise NotFoundError("Cart item not found")
        product = self.product_repo.get_by_id(UUID(item["product_id"]))
        if product["stock"] < quantity:
            raise StockError(f"Only {product['stock']} units available")
        self.cart_repo.update_item_quantity(item_id, quantity)
        return self._build_response(user_id)

    def remove_item(self, user_id: str, item_id: str) -> CartResponse:
        cart = self.cart_repo.get_or_create_cart(user_id)
        self.cart_repo.remove_item(item_id, cart["id"])
        return self._build_response(user_id)