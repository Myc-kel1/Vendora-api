# Payment Endpoints Quick Reference

## Summary

Three endpoints implement complete Paystack payment processing:

| Endpoint | Method | Auth | Purpose |
|----------|--------|------|---------|
| `/payments/initialize` | POST | ✓ Required | Start payment, get checkout URL |
| `/payments/verify/{reference}` | POST | ✓ Required | Check payment status |
| `/payments/webhook` | POST | ✗ Public | Receive Paystack webhooks |

---

## 1️⃣ Initialize Payment

**Request:**
```bash
POST /payments/initialize
Authorization: Bearer {user_token}
Content-Type: application/json

{
  "order_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Success Response (200 OK):**
```json
{
  "authorization_url": "https://checkout.paystack.com/...",
  "access_code": "2qs6pq3fme",
  "reference": "ref_123456789"
}
```

**What happens:**
1. Backend validates order exists & belongs to user
2. Calls Paystack: `/transaction/initialize`
3. Stores reference on order
4. Returns checkout URL for redirect

**Next step:** Redirect user to `authorization_url`

---

## 2️⃣ Verify Payment

**Request:**
```bash
POST /payments/verify/ref_123456789
Authorization: Bearer {user_token}
```

**Success Response (200 OK):**
```json
{
  "status": "paid",
  "order_id": "550e8400-e29b-41d4-a716-446655440000",
  "amount": 50000.00,
  "paid_at": "2026-05-01T14:30:00Z"
}
```

**Possible Status Values:**
- `paid` - Payment complete ✓
- `pending` - Still processing ⏳
- `failed` - Payment failed ✗

**What happens:**
1. Backend validates user owns this order
2. Re-verifies with Paystack API
3. Updates order status if needed
4. Returns authoritative payment status

**When to call:** After user returns from Paystack checkout

---

## 3️⃣ Paystack Webhook

**Endpoint (public, no auth required):**
```
POST /payments/webhook
x-paystack-signature: {hmac_signature}

{
  "event": "charge.success",
  "data": {
    "reference": "ref_123456789",
    "status": "success",
    ...
  }
}
```

**Always Returns (200 OK):**
```json
{
  "status": "success",
  "order_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Security:**
- ✅ Signature verified with webhook secret
- ✅ Transaction re-verified with Paystack
- ✅ Always returns 200 (Paystack requirement)

**Events Processed:**
- `charge.success` → Order marked "paid" ✓
- `charge.failed` → Order marked "failed" ✗
- Others → Logged and ignored

**Configuration:**
Add to Paystack Dashboard → Settings → Webhook:
- URL: `https://your-api.com/payments/webhook`
- Events: `charge.success`, `charge.failed`

---

## Error Responses

### 401 Unauthorized
```json
{
  "error": "Authentication required"
}
```
- Missing/invalid Bearer token
- Apply Bearer token to header

### 403 Forbidden
```json
{
  "error": "This endpoint requires admin privileges..."
}
```
- User doesn't own the order
- Check order_id and user

### 404 Not Found
```json
{
  "error": "Resource not found"
}
```
- Order or reference doesn't exist
- Verify order_id/reference is correct

### 422 Unprocessable Entity
```json
{
  "error": "Validation error"
}
```
- Order not in "pending" status (already paid/failed)
- Invalid order_id format

---

## Complete Payment Flow

```
1. Frontend gets order total
2. User clicks "Pay Now"
3. POST /payments/initialize
   ↓
4. Receive authorization_url + reference
5. Redirect user to Paystack
6. User completes payment form
7. Paystack redirects user back (client callback)
   + Paystack sends POST /payments/webhook (backend)
8. Frontend calls POST /payments/verify/{reference}
9. Receive payment status
10. Show success/failure message
```

---

## File Locations

- **Endpoints:** [app/api/customer/payments.py](app/api/customer/payments.py)
- **Service:** [app/services/payment_service.py](app/services/payment_service.py)
- **Schemas:** [app/schemas/payment.py](app/schemas/payment.py)
- **Full Docs:** [PAYSTACK_INTEGRATION.md](PAYSTACK_INTEGRATION.md)

---

## Best Practices

✅ **DO:**
- Use `/payments/verify/{reference}` to confirm payment after redirect
- Store `reference` from initialize response
- Always validate user authentication for initialize & verify
- Handle webhook with 200 response (always)
- Periodically poll verify endpoint for pending payments

❌ **DON'T:**
- Trust client-side Paystack callback alone
- Skip webhook signature verification
- Return non-200 from webhook endpoint
- Allow users to verify payments for orders they don't own
- Call initialize on non-pending orders

---

## Testing

### Test Initialize
```bash
curl -X POST http://localhost:8000/payments/initialize \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"order_id": "550e8400-e29b-41d4-a716-446655440000"}'
```

### Test Verify
```bash
curl -X POST http://localhost:8000/payments/verify/ref_123456789 \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Test Webhook (Local)
```bash
# Generate HMAC signature
PAYLOAD='{"event":"charge.success","data":{"reference":"ref_test"}}'
SECRET="your_webhook_secret"
SIGNATURE=$(echo -n "$PAYLOAD" | openssl dgst -sha512 -mac HMAC -macopt "key=$SECRET" | cut -d' ' -f2)

# Send webhook
curl -X POST http://localhost:8000/payments/webhook \
  -H "Content-Type: application/json" \
  -H "x-paystack-signature: $SIGNATURE" \
  -d "$PAYLOAD"
```

---

## Environment Setup

Add to `.env`:
```bash
# Paystack Credentials (from dashboard.paystack.com)
PAYSTACK_SECRET_KEY="sk_live_..."
PAYSTACK_PUBLIC_KEY="pk_live_..."
PAYSTACK_WEBHOOK_SECRET="your_secret_..."
```

## API Documentation

Auto-generated docs available at:
- Swagger UI: `/docs`
- ReDoc: `/redoc`
- OpenAPI JSON: `/openapi.json`

(Note: Webhook endpoint excluded from schema for security)
