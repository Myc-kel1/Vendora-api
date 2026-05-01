"""
Payment Service — Paystack integration.

Security rules:
  - Payment confirmed ONLY via webhook — never via client callback
  - HMAC-SHA512 signature verified before processing any webhook
  - Bad signature → log + return 200 dict (Paystack needs 200 or it retries)
  - Transaction re-verified directly with Paystack API after webhook receipt
  - charge.failed event handled — order marked failed
  - Idempotency: already-paid orders acknowledged without re-processing
"""
import hashlib
import hmac
import json

import httpx

from app.core.config import get_settings
from app.core.exceptions import NotFoundError, PaymentError
from app.core.logging import get_logger
from app.repositories.order_repository import OrderRepository
from app.schemas.payment import PaymentInitRequest, PaymentInitResponse, PaymentVerifyResponse

logger = get_logger(__name__)
PAYSTACK_BASE = "https://api.paystack.co"


class PaymentService:
    def __init__(self):
        self.settings   = get_settings()
        self.order_repo = OrderRepository()

    def initialize_payment(self, payload: PaymentInitRequest,
                            user_id: str, user_email: str) -> PaymentInitResponse:
        from app.core.exceptions import ForbiddenError
        order = self.order_repo.get_order_by_id(str(payload.order_id))
        if order["user_id"] != user_id:
            raise ForbiddenError("You do not have access to this order")
        if order["status"] != "pending":
            raise PaymentError(f"Order is not payable (status: {order['status']})")

        amount_kobo = int(float(order["total_amount"]) * 100)
        res = self._call_paystack("POST", "/transaction/initialize", {
            "email":    user_email,
            "amount":   amount_kobo,
            "metadata": {"order_id": str(payload.order_id)},
        })

        reference = res["data"]["reference"]
        self.order_repo.set_payment_reference(str(payload.order_id), reference)
        logger.info("payment_initialized", order_id=str(payload.order_id), reference=reference)
        return PaymentInitResponse(
            authorization_url=res["data"]["authorization_url"],
            access_code=res["data"]["access_code"],
            reference=reference,
        )

    def handle_webhook(self, raw_body: bytes, signature: str) -> dict:
        """
        Always returns a dict (HTTP layer always returns 200).
        Paystack treats any non-200 as delivery failure and retries indefinitely.
        """
        try:
            self._verify_signature(raw_body, signature)
        except PaymentError:
            logger.error("webhook_invalid_signature")
            return {"status": "rejected", "reason": "invalid_signature"}

        try:
            event = json.loads(raw_body)
        except json.JSONDecodeError:
            return {"status": "rejected", "reason": "invalid_json"}

        event_type = event.get("event")
        reference  = event.get("data", {}).get("reference")
        logger.info("webhook_received", event_type=event_type, reference=reference)

        if event_type == "charge.success":
            return self._handle_charge_success(reference)
        if event_type == "charge.failed":
            return self._handle_charge_failed(reference)
        return {"status": "ignored", "event": event_type}

    def verify_payment(self, reference: str, user_id: str) -> PaymentVerifyResponse:
        """
        Verify a payment status for a user's order.

        Best practice: User can verify their payment status without relying solely on webhook.
        Still calls Paystack API for fresh data and validates user ownership of order.

        Raises:
          ForbiddenError — user does not own this order
          NotFoundError — order not found
          PaymentError — Paystack API error
        """
        from app.core.exceptions import ForbiddenError
        
        order = self.order_repo.get_order_by_payment_reference(reference)
        if not order:
            raise NotFoundError(f"No order found for reference: {reference}")
        
        if order["user_id"] != user_id:
            raise ForbiddenError("You do not have access to this order")

        # Re-verify with Paystack API for authoritative status
        res = self._call_paystack("GET", f"/transaction/verify/{reference}")
        paystack_status = res.get("data", {}).get("status")
        
        # Map Paystack statuses to our order status
        if paystack_status == "success" and order["status"] != "paid":
            self.order_repo.update_order_status(order["id"], "paid")
            order["status"] = "paid"
            logger.info("payment_verified_and_updated", order_id=order["id"])
        elif paystack_status == "failed" and order["status"] not in ("failed", "cancelled"):
            self.order_repo.update_order_status(order["id"], "failed")
            order["status"] = "failed"
            logger.info("payment_failed_verified", order_id=order["id"])

        return PaymentVerifyResponse(
            status=order["status"],
            order_id=order["id"],
            amount=float(order["total_amount"]),
            paid_at=order.get("paid_at"),
        )

    def _handle_charge_success(self, reference: str | None) -> dict:
        if not reference:
            return {"status": "ignored", "reason": "missing_reference"}
        if not self._verify_transaction(reference):
            logger.error("payment_verification_failed", reference=reference)
            return {"status": "rejected", "reason": "verification_failed"}
        order = self.order_repo.get_order_by_payment_reference(reference)
        if not order:
            return {"status": "ignored", "reason": "order_not_found"}
        if order["status"] == "paid":
            return {"status": "already_paid", "order_id": order["id"]}
        self.order_repo.update_order_status(order["id"], "paid")
        logger.info("payment_confirmed", order_id=order["id"])
        return {"status": "success", "order_id": order["id"]}

    def _handle_charge_failed(self, reference: str | None) -> dict:
        if not reference:
            return {"status": "ignored", "reason": "missing_reference"}
        order = self.order_repo.get_order_by_payment_reference(reference)
        if not order:
            return {"status": "ignored", "reason": "order_not_found"}
        if order["status"] in ("paid", "cancelled"):
            return {"status": "ignored", "reason": f"order_already_{order['status']}"}
        self.order_repo.update_order_status(order["id"], "failed")
        logger.info("payment_failed", order_id=order["id"])
        return {"status": "failed", "order_id": order["id"]}

    def _verify_signature(self, raw_body: bytes, signature: str) -> None:
        expected = hmac.new(
            self.settings.paystack_webhook_secret.encode(),
            raw_body, hashlib.sha512
        ).hexdigest()
        if not hmac.compare_digest(expected, signature):
            raise PaymentError("Invalid webhook signature")

    def _verify_transaction(self, reference: str) -> bool:
        try:
            res = self._call_paystack("GET", f"/transaction/verify/{reference}")
            return res.get("data", {}).get("status") == "success"
        except Exception as e:
            logger.error("transaction_verify_error", reference=reference, error=str(e))
            return False

    def _call_paystack(self, method: str, path: str, data: dict | None = None) -> dict:
        headers = {"Authorization": f"Bearer {self.settings.paystack_secret_key}"}
        url = f"{PAYSTACK_BASE}{path}"
        with httpx.Client(timeout=30) as client:
            res = client.get(url, headers=headers) if method == "GET" \
                  else client.post(url, json=data, headers=headers)
        if res.status_code not in (200, 201):
            raise PaymentError(f"Paystack API error: {res.status_code}")
        return res.json()