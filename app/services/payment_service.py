"""
Payment Service — Paystack Integration.

Security rules:
- Payment is ONLY confirmed via webhook (never via client-side callback)
- Webhook signature is verified using HMAC-SHA512 before processing
- Bad signature → log + return rejection dict (still 200 to Paystack)
- Payment reference stored on order for idempotent webhook handling
- charge.failed event handled — order marked failed
- Transaction re-verified directly with Paystack API after webhook receipt
"""
import hashlib
import hmac
import json

import httpx

from app.core.config import get_settings
from app.core.exceptions import NotFoundError, PaymentError
from app.core.logging import get_logger
from app.repositories.order_repository import OrderRepository
from app.schemas.payment import PaymentInitRequest, PaymentInitResponse

logger = get_logger(__name__)

PAYSTACK_BASE_URL = "https://api.paystack.co"


class PaymentService:
    def __init__(self):
        self.settings = get_settings()
        self.order_repo = OrderRepository()

    def initialize_payment(
        self,
        payload: PaymentInitRequest,
        user_id: str,
        user_email: str,
    ) -> PaymentInitResponse:
        """
        Initialize a Paystack transaction for an order.

        Returns a payment URL that the frontend redirects the user to.
        The reference is stored on the order so the webhook can find it.
        """
        order = self.order_repo.get_order_by_id(str(payload.order_id))

        # Ownership check: prevent user A from paying for user B's order
        if order["user_id"] != user_id:
            from app.core.exceptions import ForbiddenError
            raise ForbiddenError("You do not have access to this order")

        if order["status"] != "pending":
            raise PaymentError(
                f"Order is not in a payable state (status: {order['status']})"
            )

        # Amount in kobo (Paystack uses smallest currency unit)
        amount_kobo = int(float(order["total_amount"]) * 100)

        response = self._call_paystack(
            method="POST",
            path="/transaction/initialize",
            data={
                "email": user_email,
                "amount": amount_kobo,
                "metadata": {"order_id": str(payload.order_id)},
            },
        )

        reference = response["data"]["reference"]

        # Store reference on order for webhook lookup
        self.order_repo.set_payment_reference(str(payload.order_id), reference)

        logger.info(
            "payment_initialized",
            order_id=str(payload.order_id),
            reference=reference,
        )

        return PaymentInitResponse(
            authorization_url=response["data"]["authorization_url"],
            access_code=response["data"]["access_code"],
            reference=reference,
        )

    def handle_webhook(self, raw_body: bytes, signature: str) -> dict:
        """
        Process a Paystack webhook event.

        Steps:
        1. Verify HMAC-SHA512 signature — if invalid, log and return rejection
           (still returns a dict, caller sends 200 so Paystack stops retrying)
        2. Parse event type
        3. charge.success → re-verify with Paystack API → mark order paid
        4. charge.failed  → mark order failed
        5. All other events → acknowledge and ignore

        IMPORTANT: This method never raises. All errors are caught, logged,
        and returned as status dicts so the HTTP layer can always return 200.
        """
        # Step 1: Verify signature — invalid sig is logged but still 200
        try:
            self._verify_webhook_signature(raw_body, signature)
        except PaymentError:
            logger.error("webhook_invalid_signature — rejecting but returning 200")
            return {"status": "rejected", "reason": "invalid_signature"}

        try:
            event = json.loads(raw_body)
        except json.JSONDecodeError:
            logger.error("webhook_invalid_json")
            return {"status": "rejected", "reason": "invalid_json"}

        event_type = event.get("event")
        data = event.get("data", {})
        reference = data.get("reference")

        logger.info("webhook_received", event_type=event_type, reference=reference)

        if event_type == "charge.success":
            return self._handle_charge_success(reference)

        if event_type == "charge.failed":
            return self._handle_charge_failed(reference)

        # Unhandled event types — acknowledged, Paystack won't retry
        return {"status": "ignored", "event": event_type}

    # ─── Event Handlers ───────────────────────────────────────────────────────

    def _handle_charge_success(self, reference: str | None) -> dict:
        """Mark order as paid after re-verifying with Paystack."""
        if not reference:
            logger.warning("charge_success_missing_reference")
            return {"status": "ignored", "reason": "missing_reference"}

        # Re-verify transaction directly with Paystack API
        # Never trust webhook payload alone
        if not self._verify_transaction(reference):
            logger.error("payment_verification_failed", reference=reference)
            return {"status": "rejected", "reason": "verification_failed"}

        order = self.order_repo.get_order_by_payment_reference(reference)
        if not order:
            logger.error("webhook_order_not_found", reference=reference)
            return {"status": "ignored", "reason": "order_not_found"}

        # Idempotency: already processed
        if order["status"] == "paid":
            logger.info("webhook_already_paid", order_id=order["id"])
            return {"status": "already_paid", "order_id": order["id"]}

        self.order_repo.update_order_status(order["id"], "paid")
        logger.info("payment_confirmed", order_id=order["id"], reference=reference)
        return {"status": "success", "order_id": order["id"]}

    def _handle_charge_failed(self, reference: str | None) -> dict:
        """Mark order as failed when Paystack reports charge failure."""
        if not reference:
            logger.warning("charge_failed_missing_reference")
            return {"status": "ignored", "reason": "missing_reference"}

        order = self.order_repo.get_order_by_payment_reference(reference)
        if not order:
            logger.warning("charge_failed_order_not_found", reference=reference)
            return {"status": "ignored", "reason": "order_not_found"}

        if order["status"] in ("paid", "cancelled"):
            # Don't overwrite terminal positive states
            return {"status": "ignored", "reason": f"order_already_{order['status']}"}

        self.order_repo.update_order_status(order["id"], "failed")
        logger.info("payment_failed", order_id=order["id"], reference=reference)
        return {"status": "failed", "order_id": order["id"]}

    # ─── Internal Helpers ─────────────────────────────────────────────────────

    def _verify_webhook_signature(self, raw_body: bytes, signature: str) -> None:
        """
        Verify Paystack webhook using HMAC-SHA512.
        Paystack signs the raw request body with our secret key.
        Raises PaymentError if signature doesn't match.
        """
        expected = hmac.new(
            self.settings.paystack_webhook_secret.encode("utf-8"),
            raw_body,
            hashlib.sha512,
        ).hexdigest()

        if not hmac.compare_digest(expected, signature):
            raise PaymentError("Invalid webhook signature")

    def _verify_transaction(self, reference: str) -> bool:
        """
        Directly verify a transaction with Paystack API.
        Returns True only if Paystack confirms status is 'success'.
        """
        try:
            response = self._call_paystack("GET", f"/transaction/verify/{reference}")
            return response.get("data", {}).get("status") == "success"
        except Exception as e:
            logger.error("transaction_verify_error", reference=reference, error=str(e))
            return False

    def _call_paystack(self, method: str, path: str, data: dict | None = None) -> dict:
        """Make an authenticated request to the Paystack API."""
        headers = {
            "Authorization": f"Bearer {self.settings.paystack_secret_key}",
            "Content-Type": "application/json",
        }
        url = f"{PAYSTACK_BASE_URL}{path}"

        with httpx.Client(timeout=30) as client:
            if method == "GET":
                response = client.get(url, headers=headers)
            else:
                response = client.post(url, json=data, headers=headers)

        if response.status_code not in (200, 201):
            logger.error(
                "paystack_api_error",
                status=response.status_code,
                path=path,
            )
            raise PaymentError(f"Paystack API error: {response.status_code}")

        return response.json()
