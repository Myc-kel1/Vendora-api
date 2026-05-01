# Paystack Payment Integration

## Overview

Complete Paystack payment integration with secure webhook handling, idempotent processing, and transaction verification. All endpoints implement best practices for payment security and reliability.

## Endpoints

### 1. Initialize Payment
**Endpoint:** `POST /payments/initialize`

**Authentication:** Required (Bearer Token)

**Request Body:**
```json
{
  "order_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Response (200 OK):**
```json
{
  "authorization_url": "https://checkout.paystack.com/...",
  "access_code": "2qs6pq3fme",
  "reference": "ref_123456789"
}
```

**Description:**
- Starts a new Paystack payment for a pending order
- Validates order belongs to authenticated user
- Converts order total to kobo (1 NGN = 100 kobo)
- Stores payment reference on order for webhook lookup
- Returns Paystack checkout URL for user redirect

**Error Responses:**
- `401 Unauthorized` - Missing/invalid authentication token
- `403 Forbidden` - Order does not belong to user
- `404 Not Found` - Order not found
- `422 Unprocessable Entity` - Order not in "pending" status

**Client Flow:**
1. User initiates checkout
2. Frontend calls `/payments/initialize` with order_id
3. Redirect user to `authorization_url`
4. User completes payment on Paystack
5. Paystack redirects user back to frontend (via callback URL in dashboard)
6. Frontend calls `/payments/verify/{reference}` to confirm

### 2. Verify Payment
**Endpoint:** `POST /payments/verify/{reference}`

**Authentication:** Required (Bearer Token)

**Path Parameters:**
- `reference` (string) - Paystack transaction reference from initialization

**Response (200 OK):**
```json
{
  "status": "paid",
  "order_id": "550e8400-e29b-41d4-a716-446655440000",
  "amount": 50000.00,
  "paid_at": "2026-05-01T14:30:00Z"
}
```

**Description:**
- Verifies payment status for a specific transaction
- Re-validates with Paystack API for authoritative status
- Checks user ownership of associated order
- Updates order status in database if needed
- Returns current payment/order status

**Possible Statuses:**
- `paid` - Payment confirmed
- `pending` - Payment still processing
- `failed` - Payment failed

**Error Responses:**
- `401 Unauthorized` - Missing/invalid authentication token
- `403 Forbidden` - User does not own this order
- `404 Not Found` - Order/reference not found

**Best Practices:**
- Call immediately after user returns from Paystack
- Call periodically to check async payment status
- **DO NOT** rely solely on client-side callback
- Backend webhook is authoritative confirmation

### 3. Paystack Webhook
**Endpoint:** `POST /payments/webhook`

**Authentication:** None (public)

**Headers:**
- `x-paystack-signature` (required) - HMAC-SHA512 signature

**Payload (example):**
```json
{
  "event": "charge.success",
  "data": {
    "id": 12345,
    "reference": "ref_123456789",
    "amount": 5000000,
    "paid_at": "2026-05-01T14:30:00Z",
    "status": "success"
  }
}
```

**Response (always 200 OK):**
```json
{
  "status": "success",
  "order_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Description:**
- Receives events from Paystack (charge.success, charge.failed)
- Verifies HMAC-SHA512 signature using webhook secret
- Re-verifies transaction with Paystack API for security
- Updates order status in database
- Always returns HTTP 200 (Paystack requirement)

**Security:**
- ✅ Signature verification before processing
- ✅ Invalid signatures logged, request ignored
- ✅ Transaction re-verified with Paystack
- ✅ Idempotent: already-paid orders acknowledged without re-processing
- ✅ Always returns 200 (Paystack retry logic requirement)

**Events Handled:**
- `charge.success` - Order marked as "paid"
- `charge.failed` - Order marked as "failed"
- Other events - Logged and ignored

**Configuration:**
Add webhook URL in [Paystack Dashboard](https://dashboard.paystack.com):
- Settings → Webhook
- URL: `https://your-api.com/payments/webhook`
- Events: `charge.success`, `charge.failed`

## Payment Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│ Client (Frontend)                                               │
└─────────────────────────────────────────────────────────────────┘
         │
         │ 1. POST /payments/initialize (order_id)
         ↓
┌─────────────────────────────────────────────────────────────────┐
│ Backend API                                                     │
│ - Validate order exists & belongs to user                       │
│ - Call Paystack: POST /transaction/initialize                   │
│ - Store reference on order                                      │
└─────────────────────────────────────────────────────────────────┘
         │
         │ 2. Return authorization_url
         ↓
┌─────────────────────────────────────────────────────────────────┐
│ Client (Frontend)                                               │
│ - Redirect to authorization_url                                 │
└─────────────────────────────────────────────────────────────────┘
         │
         ↓ 3. User fills payment form on Paystack (user's browser)
┌─────────────────────────────────────────────────────────────────┐
│ Paystack Checkout (Hosted)                                      │
└─────────────────────────────────────────────────────────────────┘
         │
         ├─→ 4a. Redirect to frontend callback URL (client-side)
         │
         └─→ 4b. POST /payments/webhook (backend-to-backend)
             └─→ ✅ AUTHORITATIVE CONFIRMATION
         ↓
┌─────────────────────────────────────────────────────────────────┐
│ Client (Frontend)                                               │
│ - User redirected back                                          │
│ - Call POST /payments/verify/{reference}                        │
└─────────────────────────────────────────────────────────────────┘
         │
         ↓
┌─────────────────────────────────────────────────────────────────┐
│ Backend API                                                     │
│ - Verify with Paystack API                                      │
│ - Return payment status                                         │
└─────────────────────────────────────────────────────────────────┘
```

## Error Handling

### Invalid Signature (Webhook)
```json
{
  "status": "rejected",
  "reason": "invalid_signature"
}
```
- Logged as warning
- Webhook ignored
- HTTP 200 returned (Paystack requirement)

### Verification Failed
```json
{
  "status": "rejected",
  "reason": "verification_failed"
}
```
- Transaction re-verification with Paystack failed
- Order NOT marked as paid
- Investigation required (check Paystack logs)

### Order Not Found
```json
{
  "status": "ignored",
  "reason": "order_not_found"
}
```
- Reference exists but no order found
- Possible race condition or data inconsistency
- Logged for investigation

### Already Paid (Idempotency)
```json
{
  "status": "already_paid",
  "order_id": "550e8400-e29b-41d4-a716-446655440000"
}
```
- Payment already processed
- Webhook duplicate (Paystack retried)
- No action needed, order remains paid

## Security Best Practices Implemented

✅ **Webhook Signature Verification**
- HMAC-SHA512 signature verified before processing
- Invalid signatures rejected silently
- Webhook secret stored in environment variables

✅ **Transaction Re-Verification**
- Each webhook calls Paystack API to verify status
- Prevents man-in-the-middle attacks
- Authoritative confirmation from Paystack

✅ **Idempotent Processing**
- Already-paid orders acknowledged without re-processing
- Safe retry handling for duplicate webhooks
- No double-charging possible

✅ **User Ownership Validation**
- All endpoints validate order belongs to authenticated user
- Prevents unauthorized payment status checks
- Enforced at service layer

✅ **Order Status Validation**
- Only pending orders can be paid
- Already-paid/failed orders cannot be re-initialized
- Prevents payment state confusion

✅ **Timeout Protection**
- Paystack API calls have 30-second timeout
- Prevents hanging requests
- Errors logged for investigation

✅ **Comprehensive Logging**
- All payment events logged with context
- Webhook events tracked (reference, event type)
- Errors include full context for debugging

## Environment Variables Required

```bash
PAYSTACK_SECRET_KEY="sk_live_xxx"              # From Paystack dashboard
PAYSTACK_PUBLIC_KEY="pk_live_xxx"              # For frontend integration
PAYSTACK_WEBHOOK_SECRET="your_webhook_secret"  # From Paystack dashboard
```

## Testing

### Initialize Payment (Success)
```bash
curl -X POST http://localhost:8000/payments/initialize \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "order_id": "550e8400-e29b-41d4-a716-446655440000"
  }'
```

### Verify Payment (Success)
```bash
curl -X POST http://localhost:8000/payments/verify/ref_123456789 \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Test Webhook Locally
```bash
# Generate HMAC-SHA512 signature for test payload
export PAYLOAD='{"event":"charge.success","data":{"reference":"ref_test"}}'
export SECRET="your_webhook_secret"
SIGNATURE=$(echo -n "$PAYLOAD" | openssl dgst -sha512 -mac HMAC -macopt "key=$SECRET" | cut -d' ' -f2)

curl -X POST http://localhost:8000/payments/webhook \
  -H "Content-Type: application/json" \
  -H "x-paystack-signature: $SIGNATURE" \
  -d "$PAYLOAD"
```

## Related Documentation

- [Paystack API Docs](https://paystack.com/docs/api/)
- [Paystack Events](https://paystack.com/docs/development/integration/webhooks/)
- [Paystack Webhook Security](https://paystack.com/docs/development/integration/webhooks/#securing-your-webhook)
