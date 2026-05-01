# Paystack Payment Endpoints - Complete API Specification

## Base URL
```
http://localhost:8000  (development)
https://your-api.com   (production)
```

---

## Endpoint 1: Initialize Payment

### Request
```
POST /payments/initialize
```

### Authentication
```
Authorization: Bearer {access_token}
Content-Type: application/json
```

### Request Body
```json
{
  "order_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### Response (200 OK)
```json
{
  "authorization_url": "https://checkout.paystack.com/...",
  "access_code": "2qs6pq3fme",
  "reference": "ref_123456789"
}
```

### Response (401 Unauthorized)
```json
{
  "error": "Authentication required"
}
```

### Response (403 Forbidden)
```json
{
  "error": "You do not have permission to perform this action"
}
```

### Response (404 Not Found)
```json
{
  "error": "Resource not found"
}
```

### Response (422 Unprocessable Entity)
```json
{
  "error": "Validation error"
}
```
or
```json
{
  "error": "Order is not payable (status: paid)"
}
```

### Business Logic
1. Validate user is authenticated
2. Get order by ID from database
3. Validate order exists
4. Validate order status == "pending"
5. Validate order belongs to authenticated user
6. Convert order total amount to kobo (multiply by 100)
7. Call Paystack API: `POST https://api.paystack.co/transaction/initialize`
8. Store payment reference on order
9. Log payment initialization
10. Return authorization URL and reference

### Example cURL
```bash
curl -X POST http://localhost:8000/payments/initialize \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -H "Content-Type: application/json" \
  -d '{
    "order_id": "550e8400-e29b-41d4-a716-446655440000"
  }'
```

---

## Endpoint 2: Verify Payment

### Request
```
POST /payments/verify/{reference}
```

### Path Parameters
| Name | Type | Description |
|------|------|-------------|
| reference | string | Paystack transaction reference |

### Authentication
```
Authorization: Bearer {access_token}
```

### Request Body
(none)

### Response (200 OK)
```json
{
  "status": "paid",
  "order_id": "550e8400-e29b-41d4-a716-446655440000",
  "amount": 50000.00,
  "paid_at": "2026-05-01T14:30:00Z"
}
```

### Response (200 OK - Pending)
```json
{
  "status": "pending",
  "order_id": "550e8400-e29b-41d4-a716-446655440000",
  "amount": 50000.00,
  "paid_at": null
}
```

### Response (200 OK - Failed)
```json
{
  "status": "failed",
  "order_id": "550e8400-e29b-41d4-a716-446655440000",
  "amount": 50000.00,
  "paid_at": null
}
```

### Response (401 Unauthorized)
```json
{
  "error": "Authentication required"
}
```

### Response (403 Forbidden)
```json
{
  "error": "You do not have permission to perform this action"
}
```

### Response (404 Not Found)
```json
{
  "error": "Resource not found"
}
```

### Business Logic
1. Validate user is authenticated
2. Get order by payment reference from database
3. Validate order exists
4. Validate order belongs to authenticated user
5. Call Paystack API: `GET https://api.paystack.co/transaction/verify/{reference}`
6. Get payment status from Paystack response
7. If status changed:
   - If "success" and order not paid → update order status to "paid"
   - If "failed" and order not failed → update order status to "failed"
8. Log verification and any status updates
9. Return payment status with order details

### Example cURL
```bash
curl -X POST http://localhost:8000/payments/verify/ref_123456789 \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

---

## Endpoint 3: Paystack Webhook

### Request
```
POST /payments/webhook
```

### Headers
| Name | Value | Description |
|------|-------|-------------|
| x-paystack-signature | string | HMAC-SHA512 signature |
| Content-Type | application/json | JSON payload |

### Request Body (charge.success)
```json
{
  "event": "charge.success",
  "data": {
    "id": 12345,
    "reference": "ref_123456789",
    "amount": 5000000,
    "paid_at": "2026-05-01T14:30:00Z",
    "status": "success",
    "customer": {
      "email": "user@example.com"
    }
  }
}
```

### Request Body (charge.failed)
```json
{
  "event": "charge.failed",
  "data": {
    "id": 12345,
    "reference": "ref_123456789",
    "amount": 5000000,
    "status": "failed",
    "customer": {
      "email": "user@example.com"
    }
  }
}
```

### Response (always 200 OK)
```json
{
  "status": "success",
  "order_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### Response (invalid signature, still 200 OK)
```json
{
  "status": "rejected",
  "reason": "invalid_signature"
}
```

### Response (already processed, still 200 OK)
```json
{
  "status": "already_paid",
  "order_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### Response (other events, still 200 OK)
```json
{
  "status": "ignored",
  "event": "charge.dispute.resolve"
}
```

### Business Logic
1. Read raw request body (as bytes)
2. Extract x-paystack-signature header
3. Verify HMAC-SHA512 signature:
   - Calculate: HMAC-SHA512(webhook_secret, raw_body)
   - Compare with received signature (constant-time comparison)
   - If mismatch: log error, return 200 OK (skip processing)
4. Parse JSON payload
5. Extract event type and reference
6. Log webhook received
7. Handle based on event type:
   - **charge.success:**
     - Call Paystack API to verify transaction
     - Get order by payment reference
     - If order already paid: return "already_paid" (idempotency)
     - Otherwise: update order status to "paid"
     - Log payment confirmed
   - **charge.failed:**
     - Get order by payment reference
     - If already failed/cancelled: return "ignored"
     - Otherwise: update order status to "failed"
     - Log payment failed
   - **Other events:** return "ignored"
8. **Always return 200 OK** (required by Paystack)

### Security Rules
- ✅ Signature verified before any processing
- ✅ Raw body used for signature (not parsed JSON)
- ✅ Constant-time comparison prevents timing attacks
- ✅ Invalid signature logged but not processed
- ✅ Transaction re-verified with Paystack API
- ✅ Order ownership cannot be spoofed (verified in DB)

### Example cURL (with valid signature)
```bash
# Generate signature (example)
PAYLOAD='{"event":"charge.success","data":{"reference":"ref_test"}}'
SECRET="your_webhook_secret"
SIGNATURE=$(echo -n "$PAYLOAD" | openssl dgst -sha512 -mac HMAC -macopt "key=$SECRET" | cut -d' ' -f2)

# Send webhook
curl -X POST http://localhost:8000/payments/webhook \
  -H "Content-Type: application/json" \
  -H "x-paystack-signature: $SIGNATURE" \
  -d "$PAYLOAD"
```

### Configuration in Paystack Dashboard
1. Login to [dashboard.paystack.com](https://dashboard.paystack.com)
2. Navigate to Settings → Webhook
3. Enter URL: `https://your-api.com/payments/webhook`
4. Enable events: `charge.success`, `charge.failed`
5. Copy webhook secret to environment
6. Test webhook delivery in dashboard

---

## Status Codes

| Code | Meaning | Used By |
|------|---------|---------|
| 200 | Success | All endpoints |
| 401 | Unauthorized | Initialize, Verify |
| 403 | Forbidden | Initialize, Verify |
| 404 | Not Found | Initialize, Verify |
| 422 | Validation Error | Initialize |

**Note:** Webhook always returns 200, even on errors (Paystack requirement)

---

## Error Responses

### Generic Error Format
```json
{
  "error": "Error message describing what went wrong"
}
```

### Common Errors

**Missing Authentication Token**
```json
{
  "error": "Authentication required"
}
```

**User Doesn't Own Order**
```json
{
  "error": "You do not have permission to perform this action"
}
```

**Order Not Found**
```json
{
  "error": "Resource not found"
}
```

**Order Not Payable**
```json
{
  "error": "Order is not payable (status: paid)"
}
```

**Paystack API Error**
```json
{
  "error": "Paystack API error: 429"
}
```

---

## Authentication

All endpoints except webhook require Bearer token authentication:

```
Authorization: Bearer {access_token}
```

Where `{access_token}` is a valid Supabase JWT token from user login.

To get token:
1. User logs in with email/password
2. Supabase returns access token
3. Include in Authorization header

---

## Rate Limiting

No explicit rate limiting implemented in these endpoints.
Consider adding rate limiting in production:
- Per user: 10 requests/minute
- Per IP: 100 requests/minute

---

## Timeout

Paystack API calls have 30-second timeout.
If exceeded, endpoint returns:
```json
{
  "error": "Paystack API error: timeout"
}
```

---

## Field Descriptions

### PaymentInitRequest
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| order_id | UUID | Yes | Unique identifier of pending order |

### PaymentInitResponse
| Field | Type | Description |
|-------|------|-------------|
| authorization_url | string | URL where user completes payment |
| access_code | string | Paystack access code |
| reference | string | Unique transaction reference |

### PaymentVerifyResponse
| Field | Type | Description |
|-------|------|-------------|
| status | string | Payment status: "paid", "pending", "failed" |
| order_id | string | Associated order UUID |
| amount | number | Order total amount (NGN) |
| paid_at | string \| null | ISO timestamp if paid, null otherwise |

---

## Complete Example Flow

### 1. User initiates payment
```bash
curl -X POST http://localhost:8000/payments/initialize \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"order_id": "550e8400-e29b-41d4-a716-446655440000"}'
```

**Response:**
```json
{
  "authorization_url": "https://checkout.paystack.com/...",
  "access_code": "2qs6pq3fme",
  "reference": "ref_123456789"
}
```

### 2. Frontend redirects to payment page
```javascript
window.location.href = response.authorization_url;
```

### 3. User completes payment on Paystack

### 4. Paystack sends webhook to backend
```bash
POST /payments/webhook
Header: x-paystack-signature: {hmac}
Body: {"event": "charge.success", "data": {"reference": "ref_123456789"}}
```

**Response:**
```json
{
  "status": "success",
  "order_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### 5. Frontend (after user redirect) verifies payment
```bash
curl -X POST http://localhost:8000/payments/verify/ref_123456789 \
  -H "Authorization: Bearer TOKEN"
```

**Response:**
```json
{
  "status": "paid",
  "order_id": "550e8400-e29b-41d4-a716-446655440000",
  "amount": 50000.00,
  "paid_at": "2026-05-01T14:30:00Z"
}
```

### 6. Order is now marked as paid in database ✓

---

## Troubleshooting

### 401 Unauthorized on Initialize/Verify
- **Cause:** Missing or invalid authentication token
- **Solution:** Ensure Bearer token is included in Authorization header

### 403 Forbidden on Initialize/Verify
- **Cause:** Order doesn't belong to authenticated user
- **Solution:** Verify correct order_id and that user owns the order

### 404 Not Found
- **Cause:** Order or reference doesn't exist
- **Solution:** Verify order_id and reference are correct UUIDs

### Webhook Not Being Called
- **Cause:** Webhook URL not configured in Paystack dashboard
- **Solution:** Add webhook URL in Settings → Webhook in Paystack dashboard

### Payment Status Still Pending
- **Cause:** Webhook not received or processed
- **Solution:** 
  - Check Paystack webhook delivery status
  - Verify webhook URL is publicly accessible
  - Check server logs for webhook events

---

**Specification Version:** 1.0
**Last Updated:** May 1, 2026
**Status:** Production Ready ✅
