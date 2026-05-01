# Payment Integration - Architecture & Best Practices

## Directory Structure

```
app/
├── api/customer/
│   └── payments.py                    ← API Routes (3 endpoints)
│
├── services/
│   └── payment_service.py             ← Business Logic
│       ├── initialize_payment()        ← Start Paystack transaction
│       ├── verify_payment()            ← Check payment status
│       ├── handle_webhook()            ← Process Paystack events
│       ├── _verify_signature()         ← HMAC-SHA512 validation
│       ├── _verify_transaction()       ← Paystack API call
│       ├── _handle_charge_success()    ← charge.success handler
│       ├── _handle_charge_failed()     ← charge.failed handler
│       └── _call_paystack()            ← API client
│
├── schemas/payment.py                 ← Data Models
│   ├── PaymentInitRequest
│   ├── PaymentInitResponse
│   ├── PaymentVerifyRequest
│   ├── PaymentVerifyResponse
│   └── PaymentWebhookPayload
│
├── repositories/
│   └── order_repository.py            ← Database Operations
│       ├── get_order_by_id()
│       ├── get_order_by_payment_reference()
│       ├── set_payment_reference()
│       └── update_order_status()
│
└── core/
    ├── config.py                      ← Environment Variables
    │   ├── paystack_secret_key
    │   ├── paystack_public_key
    │   └── paystack_webhook_secret
    │
    └── exceptions.py                  ← Error Classes
        ├── PaymentError
        ├── AuthenticationError
        └── ForbiddenError
```

## API Routes (Placed Correctly)

✅ **Location:** `/app/api/customer/payments.py`
- Why: Customer endpoints (authenticated users)
- Consistent with other customer routes (products, categories, orders, etc.)

✅ **Routes:**
```
POST /payments/initialize       → Initialize payment
POST /payments/verify/{ref}     → Verify payment status  
POST /payments/webhook          → Receive Paystack events
```

## Best Practices Implemented

### 1. Security

**Authentication & Authorization:**
- ✅ Initialize & Verify require Bearer token (authenticated users)
- ✅ User ownership validation (order belongs to user)
- ✅ Webhook public but signature-verified

**HMAC-SHA512 Signature Verification:**
```python
# In payment_service.py
def _verify_signature(self, raw_body: bytes, signature: str) -> None:
    expected = hmac.new(
        self.settings.paystack_webhook_secret.encode(),
        raw_body, hashlib.sha512
    ).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise PaymentError("Invalid webhook signature")
```

**Transaction Re-Verification:**
- Webhook re-verifies with Paystack API before updating order
- Prevents man-in-the-middle attacks
- Authoritative confirmation from Paystack

### 2. Idempotency

**Safe Retry Handling:**
```python
# Already-paid orders acknowledged without re-processing
if order["status"] == "paid":
    return {"status": "already_paid", "order_id": order["id"]}

self.order_repo.update_order_status(order["id"], "paid")
```

**Webhook Reliability:**
- Paystack retries failed webhooks
- Always return 200 (Paystack requirement)
- Invalid signatures logged but ignored (safe retry)

### 3. Error Handling

**Graceful Degradation:**
```python
# Bad signature → log + return 200 dict
try:
    self._verify_signature(raw_body, signature)
except PaymentError:
    logger.error("webhook_invalid_signature")
    return {"status": "rejected", "reason": "invalid_signature"}

# Always return 200 for Paystack retry logic
return JSONResponse(status_code=200, content=result)
```

**User-Friendly Errors:**
- 401: "Authentication required"
- 403: "You do not have permission to perform this action"
- 404: "Resource not found"
- 422: "Order not payable (status: failed)"

### 4. Logging

**Comprehensive Event Tracking:**
```python
logger.info("payment_initialized", order_id=order_id, reference=reference)
logger.info("webhook_received", event_type=event_type, reference=reference)
logger.info("payment_confirmed", order_id=order_id)
logger.info("payment_verified_and_updated", order_id=order_id)
logger.error("webhook_invalid_signature")
logger.error("payment_verification_failed", reference=reference)
```

### 5. Flow Control

**Webhook Always Returns 200:**
```python
@router.post("/webhook", include_in_schema=False)
async def payment_webhook(request: Request, ...):
    result = service.handle_webhook(raw_body, x_paystack_signature)
    return JSONResponse(status_code=200, content=result)  # Always 200
```

**Reason:** Paystack treats non-200 as delivery failure and retries forever (causes duplicate processing)

### 6. Data Validation

**Order Status Validation:**
```python
if order["status"] != "pending":
    raise PaymentError(f"Order is not payable (status: {order['status']})")
```

**User Ownership Validation:**
```python
if order["user_id"] != user_id:
    raise ForbiddenError("You do not have access to this order")
```

**Amount Conversion:**
```python
# Paystack uses Kobo (1 NGN = 100 Kobo)
amount_kobo = int(float(order["total_amount"]) * 100)
```

### 7. API Design

**RESTful Conventions:**
- `POST /payments/initialize` - Create new transaction
- `POST /payments/verify/{reference}` - Check status (not GET, as it calls external API)
- `POST /payments/webhook` - Receive events

**Clear Response Models:**
```python
class PaymentInitResponse(BaseModel):
    authorization_url: str   # Where to redirect
    access_code: str        # For tracking
    reference: str          # For verification

class PaymentVerifyResponse(BaseModel):
    status: str             # paid | pending | failed
    order_id: str
    amount: float
    paid_at: str | None
```

### 8. Dependency Injection

**Service Layer Pattern:**
```python
@router.post("/initialize", response_model=PaymentInitResponse)
def initialize_payment(
    payload: PaymentInitRequest,
    current_user: CurrentUser = Depends(get_current_user),
    service: PaymentService = Depends(PaymentService),  # Injected
):
    return service.initialize_payment(payload, user_id=..., user_email=...)
```

**Benefits:**
- Easy to mock for testing
- Separation of concerns
- Testable business logic

### 9. Documentation

**Docstrings on Every Function:**
```python
def initialize_payment(self, payload: PaymentInitRequest,
                        user_id: str, user_email: str) -> PaymentInitResponse:
    """
    Initialize a Paystack payment for a pending order.

    Requires:
      - User authentication
      - A pending order belonging to the user

    Returns:
      - authorization_url: Redirect user here to complete payment
      - reference: Unique transaction reference
      - access_code: Paystack access code
    """
```

**OpenAPI/Swagger Auto-Generated:**
- Fast documentation generation
- Visible in `/docs` endpoint
- Client SDK generators can consume it

### 10. Timeout Protection

**HTTP Client Timeout:**
```python
with httpx.Client(timeout=30) as client:  # 30 second timeout
    res = client.get(url, headers=headers)
```

## Error Recovery Examples

### Scenario 1: Network Failure During Initialize
```
POST /payments/initialize
  ↓
Backend calls Paystack (connection timeout)
  ↓
Exception caught, logged
  ↓
User receives PaymentError: "Paystack API error"
  ↓
User can retry (order still pending)
```

### Scenario 2: Webhook Received Twice (Idempotency)
```
Paystack sends charge.success (first time)
  ↓
Backend verifies signature, updates order to "paid"
  ↓
---
Paystack retries charge.success (second time)
  ↓
Backend verifies signature, finds order already "paid"
  ↓
Returns: {"status": "already_paid", ...}
  ↓
Order NOT updated again (idempotent)
```

### Scenario 3: Invalid Webhook Signature
```
Webhook received with bad signature
  ↓
_verify_signature() raises PaymentError
  ↓
Caught, logged as warning
  ↓
Return 200 with {"status": "rejected", "reason": "invalid_signature"}
  ↓
Paystack sees 200, won't retry (mission accomplished)
```

## Testing Checklist

- [ ] Initialize payment with valid order
- [ ] Initialize payment with non-pending order (should fail)
- [ ] Initialize payment with order from another user (should fail)
- [ ] Verify payment immediately after initialize (should show pending)
- [ ] Simulate webhook with valid signature
- [ ] Simulate webhook with invalid signature (should log but return 200)
- [ ] Send duplicate webhooks (should be idempotent)
- [ ] Verify payment after webhook received
- [ ] Test with Paystack test keys (sandbox mode)
- [ ] Load test webhooks (concurrent requests)

## Next Steps

1. **Configure Paystack Dashboard:**
   - Settings → API Keys → Copy SK and PK
   - Settings → Webhook → Add `/payments/webhook` URL

2. **Update Environment:**
   ```bash
   PAYSTACK_SECRET_KEY="sk_test_..."
   PAYSTACK_PUBLIC_KEY="pk_test_..."
   PAYSTACK_WEBHOOK_SECRET="your_webhook_secret_..."
   ```

3. **Test Endpoints:**
   - Use test keys from Paystack
   - Test all three endpoints manually
   - Verify logging output

4. **Frontend Integration:**
   - Use Paystack public key for client SDK
   - Call `/payments/initialize` to get checkout URL
   - Redirect to `authorization_url`
   - Call `/payments/verify` after user returns

5. **Deploy to Production:**
   - Switch to live Paystack keys
   - Configure webhook URL in Paystack dashboard
   - Monitor webhook delivery in Paystack dashboard
   - Test with real transactions

## File References

- [Full Integration Guide](PAYSTACK_INTEGRATION.md)
- [Quick Reference](PAYMENT_ENDPOINTS_QUICK_REFERENCE.md)
- [Routes](app/api/customer/payments.py)
- [Service](app/services/payment_service.py)
- [Schemas](app/schemas/payment.py)
