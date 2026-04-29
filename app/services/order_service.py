"""
Order Service — the critical transactional section.

Place order flow:
  1. Fetch cart items
  2. Guard: empty cart → EmptyCartError
  3. Re-validate stock for each item (race condition protection)
  4. Create order row (status=pending)
  5. Insert order_items with price snapshot
  6. Atomically deduct stock via SQL RPC (FOR UPDATE lock)
  7. Clear cart on success
  8. If stock deduction fails → mark order as 'failed', raise StockError
"""
from decimal import Decimal
from uuid import UUID

from app.core.exceptions import EmptyCartError, ForbiddenError, NotFoundError, StockError
from app.core.logging import get_logger
from app.repositories.cart_repository import CartRepository
from app.repositories.order_repository import OrderRepository
from app.repositories.product_repository import ProductRepository
from app.schemas.order import OrderListResponse, OrderResponse, OrderItemResponse

logger = get_logger(__name__)

# Valid state machine transitions
VALID_TRANSITIONS = {
    "pending":   {"paid", "failed", "cancelled"},
    "paid":      {"cancelled"},
    "failed":    {"pending"},
    "cancelled": set(),
}


class OrderService:
    def __init__(self):
        self.order_repo   = OrderRepository()
        self.cart_repo    = CartRepository()
        self.product_repo = ProductRepository()

    def _build_order_response(self, raw: dict) -> OrderResponse:
        items = [
            OrderItemResponse(
                id=i["id"], product_id=i["product_id"],
                product_name=(i.get("products") or {}).get("name", ""),
                quantity=i["quantity"],
                price=Decimal(str(i["price"])),
                subtotal=Decimal(str(i["price"])) * i["quantity"],
            )
            for i in (raw.get("order_items") or [])
        ]
        return OrderResponse(
            id=raw["id"], user_id=raw["user_id"], status=raw["status"],
            total_amount=Decimal(str(raw["total_amount"])),
            items=items, created_at=raw["created_at"],
        )

    def place_order(self, user_id: str) -> OrderResponse:
        cart = self.cart_repo.get_cart_with_items(user_id)
        cart_items = cart.get("cart_items", [])
        if not cart_items:
            raise EmptyCartError()

        # Re-validate stock (race condition protection)
        product_ids = [ci["product_id"] for ci in cart_items]
        products    = {p["id"]: p for p in self.product_repo.get_many_by_ids(product_ids)}
        for ci in cart_items:
            prod = products.get(ci["product_id"])
            if not prod or prod["stock"] < ci["quantity"]:
                available = prod["stock"] if prod else 0
                raise StockError(f"Only {available} units of '{prod['name'] if prod else ci['product_id']}' available")

        # Calculate total
        total = sum(
            Decimal(str(products[ci["product_id"]]["price"])) * ci["quantity"]
            for ci in cart_items
        )

        # Create order
        order_raw = self.order_repo.create_order(user_id, float(total), cart["id"])
        order_id  = order_raw["id"]

        try:
            # Insert order items with price snapshot
            self.order_repo.insert_order_items(order_id, [
                {
                    "product_id": ci["product_id"],
                    "quantity":   ci["quantity"],
                    "price":      float(products[ci["product_id"]]["price"]),
                }
                for ci in cart_items
            ])

            # Atomically deduct stock — raises on any insufficient stock
            for ci in cart_items:
                self.product_repo.decrement_stock(ci["product_id"], ci["quantity"])

        except Exception as exc:
            # Stock deduction failed mid-order — mark failed, preserve for audit
            self.order_repo.update_order_status(order_id, "failed")
            logger.error("order_stock_deduction_failed", order_id=order_id, error=str(exc))
            raise StockError("Stock changed during checkout — order has been cancelled")

        # Success — clear cart
        self.cart_repo.clear_cart(cart["id"])
        logger.info("order_placed", order_id=order_id, user_id=user_id, total=float(total))

        return self._build_order_response(self.order_repo.get_order_by_id(order_id))

    def get_order(self, order_id: str) -> OrderResponse:
        return self._build_order_response(self.order_repo.get_order_by_id(order_id))

    def get_order_for_user(self, order_id: str, user_id: str) -> OrderResponse:
        raw = self.order_repo.get_order_by_id(order_id)
        if raw["user_id"] != user_id:
            raise ForbiddenError("You do not have access to this order")
        return self._build_order_response(raw)

    def cancel_order(self, order_id: str, user_id: str) -> OrderResponse:
        from app.core.exceptions import ConflictError
        raw = self.order_repo.get_order_by_id(order_id)
        if raw["user_id"] != user_id:
            raise ForbiddenError("You do not have access to this order")
        if raw["status"] != "pending":
            raise ConflictError(f"Only pending orders can be cancelled (current: {raw['status']})")
        self.order_repo.update_order_status(order_id, "cancelled")
        return self.get_order(order_id)

    def get_my_orders(self, user_id: str, page=1, page_size=20) -> OrderListResponse:
        items, total = self.order_repo.get_my_orders(user_id, page, page_size)
        return OrderListResponse(items=[self._build_order_response(o) for o in items], total=total)

    def get_all_orders(self, page=1, page_size=20, status_filter=None, user_id_filter=None) -> OrderListResponse:
        items, total = self.order_repo.get_all_orders(page, page_size, status_filter, user_id_filter)
        return OrderListResponse(items=[self._build_order_response(o) for o in items], total=total)

def update_order_status(self, order_id: str, new_status: str) -> OrderResponse:
    """
    Admin: update order status following the state machine.

    Valid transitions:
      pending   → paid | failed | cancelled
      paid      → cancelled
      failed    → pending
      cancelled → (terminal — no transitions allowed)

    Raises ConflictError for invalid transitions.
    """
    from app.core.exceptions import ConflictError
    raw     = self.order_repo.get_order_by_id(order_id)
    current = raw["status"]
    allowed = VALID_TRANSITIONS.get(current, set())

    if new_status == current:
        # No-op — status unchanged, return current state
        return self._build_order_response(raw)

    if new_status not in allowed:
        allowed_str = ", ".join(sorted(allowed)) if allowed else "none (terminal state)"
        raise ConflictError(
            f"Cannot transition order from '{current}' to '{new_status}'. "
            f"Allowed transitions: {allowed_str}"
        )

    self.order_repo.update_order_status(order_id, new_status)
    logger.info("order_status_updated", order_id=order_id,
                from_status=current, to_status=new_status)
    return self.get_order(order_id)