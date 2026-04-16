from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class PaymentInitRequest(BaseModel):
    order_id: UUID


class PaymentInitResponse(BaseModel):
    authorization_url: str   # Redirect user here
    access_code: str
    reference: str           # Store this to verify later


class PaymentWebhookPayload(BaseModel):
    """
    Paystack sends this to our webhook endpoint after payment.
    We validate the signature before trusting this payload.
    """
    event: str               # e.g. "charge.success"
    data: dict               # Full event data from Paystack