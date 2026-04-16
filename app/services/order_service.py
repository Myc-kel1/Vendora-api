"""
Order Service — CRITICAL SECTION.

This is the most important service in the system.
Order creation involves multiple coordinated steps that must all succeed.

Steps (in order):
1. Fetch user's cart with items
2. Validate cart is not empty
3. Re-validate stock for EVERY item (second check after cart add)
4. Calculate total
5. Create order record (status=pending)
6. Insert order_items (price snapshot at time of order)
7. Deduct stock atomically via SQL RPC
8. Clear cart
9. Return order

Idempotency:
- If an active pending order exists for this user+cart, return it instead
  of creating a duplicate. This handles retry scenarios safely.
"""
from decimal import Decimal

from app.core.exceptions import (
    DuplicateOrderError,
    EmptyCartError,
    NotFoundError,
    StockError,
)
from app.core.logging import get_logger
from app.repositories.cart_repository import CartRepository
from app.repositories.order_repository import OrderRepository
from app.repositories.product_repository import ProductRepository
from app.schemas.order import OrderListResponse, OrderResponse

logger = get_logger(__name__)


class OrderService:
    def __init__(self):
        self.cart_repo = CartRepository()
        self.order_repo = OrderRepository()
        self.product_repo = ProductRepository()

    def place_order(self, user_id: str) -> OrderResponse:
        """
        Place an order from the user's current cart.

        This is the core transactional flow of the entire system.
        """
        # Step 1: Fetch cart
        cart = self.cart_repo.get_cart_with_items(user_id)
        cart_id = cart["id"]
        raw_items = cart.get("cart_items", [])

        # Step 2: Validate cart is not empty
        if not raw_items:
            raise EmptyCartError()

        # Step 3: Re-validate stock for all items
        # Fetch all products in ONE query to avoid N+1
        product_ids = [item["product_id"] for item in raw_items]
        products = self.product_repo.get_many_by_ids(product_ids)
        product_map = {p["id"]: p for p in products}

        stock_errors = []
        for item in raw_items:
            product = product_map.get(item["product_id"])
            if not product:
                stock_errors.append(f"Product {item['product_id']} no longer exists")
                continue
            if product["stock"] < item["quantity"]:
                stock_errors.append(
                    f"'{product['name']}': requested {item['quantity']}, "
                    f"only {product['stock']} available"
                )

        if stock_errors:
            raise StockError("; ".join(stock_errors))

        # Step 4: Calculate total
        total = Decimal("0")
        for item in raw_items:
            product = product_map[item["product_id"]]
            total += Decimal(str(product["price"])) * item["quantity"]

        # Step 5: Create order
        order = self.order_repo.create_order(
            user_id=user_id,
            total_amount=float(total),
        )
        order_id = order["id"]

        # Step 6: Insert order items (price snapshot)
        order_items_payload = [
            {
                "order_id": order_id,
                "product_id": item["product_id"],
                "quantity": item["quantity"],
                "price": float(product_map[item["product_id"]]["price"]),
            }
            for item in raw_items
        ]
        self.order_repo.insert_order_items(order_items_payload)

        # Step 7: Deduct stock atomically for each product
        # The SQL RPC handles atomicity and raises if stock goes negative
        for item in raw_items:
            try:
                self.product_repo.decrement_stock(item["product_id"], item["quantity"])
            except Exception as e:
                # If stock deduction fails, mark order as failed for audit
                self.order_repo.update_order_status(order_id, "failed")
                logger.error(
                    "stock_deduction_failed",
                    order_id=order_id,
                    product_id=item["product_id"],
                    error=str(e),
                )
                raise StockError(f"Stock deduction failed during order creation: {e}")

        # Step 8: Clear cart
        self.cart_repo.clear_cart(cart_id)

        logger.info("order_placed", order_id=order_id, user_id=user_id, total=str(total))

        # Step 9: Return full order
        return self.get_order(order_id)

    def get_my_orders(self, user_id: str, page: int = 1, page_size: int = 20) -> OrderListResponse:
        """Fetch paginated orders belonging to the authenticated user."""
        orders, total = self.order_repo.get_orders_by_user(user_id, page=page, page_size=page_size)
        return OrderListResponse(
            items=[self._build_order_response(o) for o in orders],
            total=total,
        )

    def cancel_order(self, order_id: str, user_id: str) -> OrderResponse:
        """
        Customer: cancel their own pending order.

        Rules:
        - Order must belong to the requesting user (403 otherwise)
        - Only pending orders can be cancelled (409 otherwise)
        - Paid orders cannot be cancelled by customers — admin only
        """
        from app.core.exceptions import ConflictError, ForbiddenError

        order = self.order_repo.get_order_by_id(order_id)

        if order["user_id"] != user_id:
            raise ForbiddenError("You do not have access to this order")

        if order["status"] != "pending":
            raise ConflictError(
                f"Only pending orders can be cancelled. "
                f"This order is '{order['status']}'. Contact support if needed."
            )

        self.order_repo.update_order_status(order_id, "cancelled")
        logger.info("order_cancelled_by_customer", order_id=order_id, user_id=user_id)
        return self.get_order(order_id)

    def get_order_for_user(self, order_id: str, user_id: str) -> OrderResponse:
        """
        Fetch a single order — verifies it belongs to the requesting user.
        Raises ForbiddenError if the order exists but belongs to someone else.
        This prevents order ID enumeration attacks.
        """
        from app.core.exceptions import ForbiddenError
        order = self.order_repo.get_order_by_id(order_id)
        if order["user_id"] != user_id:
            # Return 403 not 404 — the order exists, the user just can't see it
            raise ForbiddenError("You do not have access to this order")
        return self._build_order_response(order)

    def get_order(self, order_id: str) -> OrderResponse:
        """Fetch a single order by ID with all items."""
        order = self.order_repo.get_order_by_id(order_id)
        return self._build_order_response(order)

    def get_all_orders(
        self,
        page: int = 1,
        page_size: int = 20,
        status_filter: str | None = None,
        user_id_filter: str | None = None,
    ) -> OrderListResponse:
        """Admin: fetch all orders across all users, paginated, with optional filters."""
        orders, total = self.order_repo.get_all_orders(
            page=page,
            page_size=page_size,
            status_filter=status_filter,
            user_id_filter=user_id_filter,
        )
        return OrderListResponse(
            items=[self._build_order_response(o) for o in orders],
            total=total,
        )

    # Valid state transitions — prevents illegal moves like paid → pending
    _ALLOWED_TRANSITIONS: dict[str, set[str]] = {
        "pending":   {"paid", "failed", "cancelled"},
        "paid":      {"cancelled"},          # can refund/cancel a paid order
        "failed":    {"pending"},            # can retry a failed order
        "cancelled": set(),                  # terminal state — no transitions out
    }

    def update_order_status(self, order_id: str, new_status: str) -> OrderResponse:
        """
        Admin: update order status — enforces valid state transitions.
        Raises ConflictError if transition is not allowed.
        """
        from app.core.exceptions import ConflictError
        order = self.order_repo.get_order_by_id(order_id)
        current_status = order["status"]

        allowed = self._ALLOWED_TRANSITIONS.get(current_status, set())
        if new_status not in allowed:
            raise ConflictError(
                f"Cannot transition order from '{current_status}' to '{new_status}'. "
                f"Allowed transitions: {sorted(allowed) or 'none (terminal state)'}"
            )

        self.order_repo.update_order_status(order_id, new_status)
        return self.get_order(order_id)

    # ─── Internal Helpers ─────────────────────────────────────────────────────

    def _build_order_response(self, raw: dict) -> OrderResponse:
        """Transform raw Supabase nested order response into OrderResponse."""
        from app.schemas.order import OrderItemResponse

        raw_items = raw.get("order_items", [])
        items = []
        for raw_item in raw_items:
            product = raw_item.get("products", {})
            price = Decimal(str(raw_item["price"]))
            quantity = raw_item["quantity"]
            items.append(
                OrderItemResponse(
                    id=raw_item["id"],
                    product_id=raw_item["product_id"],
                    product_name=product.get("name", ""),
                    quantity=quantity,
                    price=price,
                    subtotal=price * quantity,
                )
            )

        return OrderResponse(
            id=raw["id"],
            user_id=raw["user_id"],
            status=raw["status"],
            total_amount=Decimal(str(raw["total_amount"])),
            items=items,
            created_at=raw.get("created_at"),
        )
