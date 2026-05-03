"""
Customer — Payments.

Endpoints:
  POST /payments/initialize        → Start Paystack transaction (authenticated)
  POST /payments/verify/{reference}   → Verify payment status (authenticated)
  POST /payments/webhook           → Paystack webhook (public, signed)

Webhook ALWAYS returns HTTP 200 regardless of outcome.
Paystack treats non-200 as delivery failure and retries forever.
Security is enforced inside the service (HMAC verification),
not via HTTP status codes.
"""
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from app.dependencies.auth import get_current_user
from app.schemas.payment import PaymentInitRequest, PaymentInitResponse, PaymentVerifyResponse
from app.schemas.user import CurrentUser
from app.services.payment_service import PaymentService

router = APIRouter(prefix="/payments", tags=["Customer — Payments"])


@router.post("/initialize", response_model=PaymentInitResponse)
def initialize_payment(
    payload: PaymentInitRequest,
    current_user: CurrentUser = Depends(get_current_user),
    service: PaymentService = Depends(PaymentService),
):
    """
    Initialize a Paystack payment for a pending order.

    Requires:
      - User authentication
      - A pending order belonging to the user

    Returns:
      - authorization_url: Redirect user here to complete payment on Paystack
      - reference: Unique transaction reference for tracking
      - access_code: Paystack access code

    Best practice: Client redirects user to authorization_url. After payment,
    Paystack sends webhook to /payments/webhook and may redirect to /payments/callback
    if callback_url is configured. Use /payments/verify for explicit status checks.
    """
    return service.initialize_payment(payload, user_id=current_user.id, user_email=current_user.email)


@router.api_route("/verify/{reference}", methods=["GET", "POST"], response_model=PaymentVerifyResponse)
def verify_payment(
    reference: str,
    current_user: CurrentUser = Depends(get_current_user),
    service: PaymentService = Depends(PaymentService),
):
    """
    Verify the payment status of a transaction.

    Requires:
      - User authentication
      - User must own the order associated with this reference

    Returns:
      - status: "paid" | "pending" | "failed"
      - order_id: Associated order UUID
      - amount: Order total amount
      - paid_at: Timestamp if paid (may be None)

    Best practice: Call this endpoint AFTER user returns from Paystack,
    or periodically to check status. Do NOT trust client-side callback.
    This endpoint re-verifies with Paystack API for authoritative status.
    """
    return service.verify_payment(reference, user_id=current_user.id)


@router.get("/callback", response_model=PaymentVerifyResponse)
def paystack_callback(
    reference: str | None = Query(default=None),
    trxref: str | None = Query(default=None),
    service: PaymentService = Depends(PaymentService),
):
    """
    Paystack redirect callback.

    If a callback_url is configured for Paystack initialization, Paystack will
    redirect the user here with a reference. This endpoint verifies the
    transaction and updates the order status automatically.
    """
    paystack_reference = reference or trxref
    if not paystack_reference:
        raise HTTPException(status_code=400, detail="Missing Paystack reference")
    return service.complete_payment(paystack_reference)


@router.post("/webhook", include_in_schema=False)
async def payment_webhook(
    request: Request,
    x_paystack_signature: str = Header(...),
    service: PaymentService = Depends(PaymentService),
):
    """
    Paystack webhook — processes charge events.

    Security:
      - HMAC-SHA512 signature verified before processing
      - Always returns 200 (Paystack requirement for retry logic)
      - Invalid signature logged but not processed
      - Transaction re-verified with Paystack API

    Events handled:
      - charge.success → order marked as paid
      - charge.failed → order marked as failed
      - others → logged and ignored

    Note: This endpoint is NOT in OpenAPI schema (include_in_schema=False)
    as it's for backend-to-backend communication.
    """
    raw_body = await request.body()
    result   = service.handle_webhook(raw_body, x_paystack_signature)
    return JSONResponse(status_code=200, content=result)   # always 200