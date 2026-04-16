"""
Custom Exception Hierarchy.

Every custom exception extends AppError, which itself extends
FastAPI's HTTPException. This means:

  1. Each exception carries its own HTTP status_code as a class attribute
  2. The global handler in main.py catches AppError and returns a clean
     JSON body: {"error": "<detail message>"}
  3. Raising these anywhere in the service or repository layer
     automatically produces the correct HTTP response — no try/except
     needed in the route handlers

Usage:
    from app.core.exceptions import NotFoundError, StockError

    raise NotFoundError("Product abc not found")
    raise StockError()  # uses the default class-level detail message

Hierarchy:
    AppError (500)
    ├── AuthenticationError (401)
    ├── ForbiddenError (403)
    ├── NotFoundError (404)
    ├── PaymentError (402)
    ├── ValidationError (422)
    │   └── EmptyCartError (422)
    └── ConflictError (409)
        ├── StockError (409)
        └── DuplicateOrderError (409)
"""
from fastapi import HTTPException


class AppError(HTTPException):
    """
    Base class for all application-level errors.

    Subclasses declare status_code and detail as class attributes.
    The __init__ allows passing a custom detail message, falling back
    to the class-level default when none is provided.
    """
    status_code: int = 500
    detail: str = "An unexpected error occurred"

    def __init__(self, detail: str | None = None):
        super().__init__(
            status_code=self.__class__.status_code,
            detail=detail or self.__class__.detail,
        )


class AuthenticationError(AppError):
    """
    401 Unauthorized.

    Raised when:
    - Authorization header is missing
    - Bearer token is malformed, invalid, or expired
    - JWT signature verification fails
    """
    status_code = 401
    detail = "Authentication required"


class ForbiddenError(AppError):
    """
    403 Forbidden.

    Raised when:
    - A valid user token is present but the user's role is insufficient
    - A user attempts to access another user's resource (e.g. order)
    """
    status_code = 403
    detail = "You do not have permission to perform this action"


class NotFoundError(AppError):
    """
    404 Not Found.

    Raised when a requested resource does not exist in the database.
    Never reveal whether a resource exists if the user lacks permission —
    in those cases prefer ForbiddenError.
    """
    status_code = 404
    detail = "Resource not found"


class PaymentError(AppError):
    """
    402 Payment Required.

    Raised when payment initialization fails or when the Paystack API
    returns an error. Note: webhook handling never raises this — it
    returns a status dict with HTTP 200 to prevent Paystack retries.
    """
    status_code = 402
    detail = "Payment processing failed"


class ValidationError(AppError):
    """
    422 Unprocessable Entity — Business Logic Validation.

    Distinct from Pydantic's RequestValidationError (which handles
    schema-level issues). This is raised when business rules are violated
    at the service layer, e.g. attempting checkout with an empty cart.
    """
    status_code = 422
    detail = "Validation error"


class EmptyCartError(ValidationError):
    """
    422 — Checkout attempted with an empty cart.

    Raised by OrderService.place_order() when the user's cart has no items.
    """
    detail = "Cannot place an order with an empty cart"


class ConflictError(AppError):
    """
    409 Conflict.

    Raised when an operation conflicts with the current resource state,
    such as trying to cancel a paid order or creating a duplicate record.
    """
    status_code = 409
    detail = "Conflict with current state"


class StockError(ConflictError):
    """
    409 — Insufficient stock.

    Raised in two places:
    1. CartService.add_item() — when requested quantity > available stock
    2. OrderService.place_order() — when stock drops between cart add and
       checkout (race condition protection)
    """
    detail = "Insufficient stock for one or more items"


class DuplicateOrderError(ConflictError):
    """
    409 — Idempotency violation.

    Raised when a customer attempts to place a second order from a cart
    that already has a pending/paid order associated with it.
    """
    detail = "An order has already been placed for this cart"
