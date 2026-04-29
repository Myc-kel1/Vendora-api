"""
Custom exception hierarchy.

Every exception maps to an HTTP status code.
The global handler in main.py converts these to clean JSON responses.
Raising any AppError subclass anywhere in service/repository layers
automatically produces the correct HTTP response — no try/except needed
in route handlers.
"""
from fastapi import HTTPException


class AppError(HTTPException):
    status_code: int = 500
    detail: str      = "An unexpected error occurred"

    def __init__(self, detail: str | None = None):
        super().__init__(
            status_code=self.__class__.status_code,
            detail=detail or self.__class__.detail,
        )


class AuthenticationError(AppError):
    """401 — Token missing, invalid, or expired."""
    status_code = 401
    detail = "Authentication required"


class ForbiddenError(AppError):
    """403 — Authenticated but insufficient role."""
    status_code = 403
    detail = "You do not have permission to perform this action"


class NotFoundError(AppError):
    """404 — Resource not found."""
    status_code = 404
    detail = "Resource not found"


class PaymentError(AppError):
    """402 — Payment processing failure."""
    status_code = 402
    detail = "Payment processing failed"


class ValidationError(AppError):
    """422 — Business logic validation (distinct from Pydantic schema validation)."""
    status_code = 422
    detail = "Validation error"


class ConflictError(AppError):
    """409 — State conflict."""
    status_code = 409
    detail = "Conflict with current state"


class StockError(ConflictError):
    """409 — Insufficient stock."""
    detail = "Insufficient stock for one or more items"


class EmptyCartError(ValidationError):
    """422 — Cannot checkout with empty cart."""
    detail = "Cannot place an order with an empty cart"


class DuplicateOrderError(ConflictError):
    """409 — Order already placed for this cart."""
    detail = "An order has already been placed for this cart"