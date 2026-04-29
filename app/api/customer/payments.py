"""
Customer — Payments.

Webhook ALWAYS returns HTTP 200 regardless of outcome.
Paystack treats non-200 as delivery failure and retries forever.
Security is enforced inside the service (HMAC verification),
not via HTTP status codes.
"""
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
    return service.initialize_payment(payload, user_id=current_user.id, user_email=current_user.email)


@router.post("/webhook", include_in_schema=False)
async def payment_webhook(
    request: Request,
    x_paystack_signature: str = Header(...),
    service: PaymentService = Depends(PaymentService),
):
    raw_body = await request.body()
    result   = service.handle_webhook(raw_body, x_paystack_signature)
    return JSONResponse(status_code=200, content=result)   # always 200