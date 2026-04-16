from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import JSONResponse

from app.dependencies.auth import get_current_user
from app.schemas.payment import PaymentInitRequest, PaymentInitResponse
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

    Returns a payment URL. Redirect the user there to complete payment.
    Payment confirmation is handled exclusively via the webhook — never
    trust client-side callbacks.
    """
    return service.initialize_payment(
        payload,
        user_id=current_user.id,
        user_email=current_user.email,
    )


@router.post("/webhook", include_in_schema=False)
async def payment_webhook(
    request: Request,
    x_paystack_signature: str = Header(...),
    service: PaymentService = Depends(PaymentService),
):
    """
    Paystack webhook receiver.

    CRITICAL: Always returns HTTP 200 regardless of outcome.
    Paystack treats any non-200 as a delivery failure and retries
    indefinitely — bad signature, unknown reference, already-paid orders
    all get 200 back, with status in the body for our own audit trail.

    Security is enforced INSIDE the service (HMAC-SHA512 sig check),
    not by HTTP status codes.
    """
    raw_body = await request.body()
    result = service.handle_webhook(raw_body, x_paystack_signature)
    # Always 200 — Paystack contract
    return JSONResponse(status_code=200, content=result)
