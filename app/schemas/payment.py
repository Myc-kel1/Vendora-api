from uuid import UUID
from pydantic import BaseModel, Field


class PaymentInitRequest(BaseModel):
    order_id: UUID = Field(description="UUID of a pending order to pay for")


class PaymentInitResponse(BaseModel):
    authorization_url: str   # redirect user here (Paystack-hosted page)
    access_code:       str
    reference:         str   # stored on order for webhook lookup


class PaymentWebhookPayload(BaseModel):
    """
    Paystack webhook payload — documented for reference.
    The route reads raw bytes for HMAC verification BEFORE
    parsing, so this schema is not used as a route body type.
    """
    event: str
    data:  dict