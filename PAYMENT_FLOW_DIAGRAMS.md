# Paystack Integration - Complete Flow Diagrams

## 1. Payment Initialization Flow

```
┌──────────────────────────────────────────────────────────────────────┐
│ CLIENT (Frontend)                                                    │
│ - Order created with total amount                                    │
│ - User clicks "Pay Now"                                              │
└──────────────────────────────────────────────────────────────────────┘
                                ↓
            ┌───────────────────────────────────────┐
            │ POST /payments/initialize             │
            │ {order_id: "xxx"}                     │
            │ Auth: Bearer token                    │
            └───────────────────────────────────────┘
                                ↓
┌──────────────────────────────────────────────────────────────────────┐
│ BACKEND (FastAPI)                                                    │
│ 1. get_current_user() - Extract user from token                      │
│ 2. get_order_by_id() - Fetch order from DB                           │
│ 3. Validate:                                                         │
│    ✓ Order belongs to user                                           │
│    ✓ Order status == "pending"                                       │
│ 4. Convert amount: float_amount * 100 = kobo                         │
│ 5. Call Paystack API: POST /transaction/initialize                   │
│ 6. Store reference on order: set_payment_reference()                 │
│ 7. Log: payment_initialized                                          │
└──────────────────────────────────────────────────────────────────────┘
                                ↓
            ┌───────────────────────────────────────┐
            │ 200 OK                                │
            │ {                                     │
            │   authorization_url: "https://...",   │
            │   access_code: "2qs6pq3fme",          │
            │   reference: "ref_123456789"          │
            │ }                                     │
            └───────────────────────────────────────┘
                                ↓
┌──────────────────────────────────────────────────────────────────────┐
│ CLIENT (Frontend)                                                    │
│ - Redirect user to authorization_url                                 │
│ - Store reference for verification later                             │
└──────────────────────────────────────────────────────────────────────┘
                                ↓
┌──────────────────────────────────────────────────────────────────────┐
│ PAYSTACK CHECKOUT (User's Browser)                                   │
│ - User enters card details                                           │
│ - Paystack processes payment                                         │
└──────────────────────────────────────────────────────────────────────┘
```

## 2. Payment Verification Flow

```
┌──────────────────────────────────────────────────────────────────────┐
│ CLIENT (Frontend)                                                    │
│ - User returns from Paystack checkout                                │
│ - Wants to verify payment was successful                             │
└──────────────────────────────────────────────────────────────────────┘
                                ↓
            ┌───────────────────────────────────────────┐
            │ POST /payments/verify/ref_123456789       │
            │ Auth: Bearer token                        │
            └───────────────────────────────────────────┘
                                ↓
┌──────────────────────────────────────────────────────────────────────┐
│ BACKEND (FastAPI)                                                    │
│ 1. get_current_user() - Extract user from token                      │
│ 2. get_order_by_payment_reference() - Fetch order                    │
│ 3. Validate:                                                         │
│    ✓ Order exists                                                    │
│    ✓ Order belongs to user                                           │
│ 4. Call Paystack API: GET /transaction/verify/ref_123456789          │
│ 5. Check Paystack status:                                            │
│    - If "success" & order not paid → update to "paid"                │
│    - If "failed" & order not failed → update to "failed"             │
│ 6. Log: payment_verified_and_updated                                 │
│ 7. Return PaymentVerifyResponse                                      │
└──────────────────────────────────────────────────────────────────────┘
                                ↓
            ┌───────────────────────────────────────────┐
            │ 200 OK                                    │
            │ {                                         │
            │   status: "paid",                         │
            │   order_id: "xxx",                        │
            │   amount: 50000.00,                       │
            │   paid_at: "2026-05-01T14:30:00Z"         │
            │ }                                         │
            └───────────────────────────────────────────┘
                                ↓
┌──────────────────────────────────────────────────────────────────────┐
│ CLIENT (Frontend)                                                    │
│ - Show success message                                               │
│ - Update UI to show order as paid                                    │
│ - Redirect to order confirmation                                     │
└──────────────────────────────────────────────────────────────────────┘
```

## 3. Webhook Processing Flow (Authoritative)

```
┌──────────────────────────────────────────────────────────────────────┐
│ PAYSTACK SERVERS                                                     │
│ - Payment successful                                                  │
│ - Sending webhook notifications                                      │
└──────────────────────────────────────────────────────────────────────┘
                                ↓
         ┌──────────────────────────────────────────────┐
         │ POST /payments/webhook                       │
         │ Headers: {x-paystack-signature: "...hmac..."} │
         │ Body: {                                      │
         │   event: "charge.success",                   │
         │   data: {                                    │
         │     reference: "ref_123456789",              │
         │     status: "success",                       │
         │     ...                                      │
         │   }                                          │
         │ }                                            │
         └──────────────────────────────────────────────┘
                                ↓
┌──────────────────────────────────────────────────────────────────────┐
│ BACKEND (FastAPI) - Webhook Handler                                  │
│                                                                      │
│ 1. READ RAW BODY (bytes) - needed for signature verification         │
│                                                                      │
│ 2. VERIFY SIGNATURE                                                  │
│    ├─ Calculate HMAC-SHA512(webhook_secret, raw_body)                │
│    ├─ Compare with x-paystack-signature header                       │
│    └─ If mismatch:                                                   │
│        ├─ Log: "webhook_invalid_signature"                           │
│        ├─ Return 200 OK (Paystack won't retry bad sigs)              │
│        └─ DO NOT PROCESS WEBHOOK ❌                                  │
│                                                                      │
│ 3. PARSE EVENT from JSON                                             │
│                                                                      │
│ 4. HANDLE EVENT                                                      │
│    ├─ If charge.success:                                             │
│    │  ├─ Call Paystack API: verify reference                         │
│    │  ├─ Get order by reference                                      │
│    │  ├─ If already paid: return "already_paid" (idempotent)         │
│    │  ├─ Otherwise: update_order_status(order_id, "paid")            │
│    │  ├─ Log: "payment_confirmed"                                    │
│    │  └─ Return {"status": "success"}                                │
│    │                                                                 │
│    ├─ If charge.failed:                                              │
│    │  ├─ Get order by reference                                      │
│    │  ├─ If already failed: skip                                     │
│    │  ├─ Otherwise: update_order_status(order_id, "failed")          │
│    │  ├─ Log: "payment_failed"                                       │
│    │  └─ Return {"status": "failed"}                                 │
│    │                                                                 │
│    └─ Other events: return {"status": "ignored"}                     │
│                                                                      │
│ 5. ALWAYS RETURN 200 OK ← CRITICAL                                   │
│    (Paystack treats non-200 as delivery failure & retries forever)   │
└──────────────────────────────────────────────────────────────────────┘
                                ↓
         ┌──────────────────────────────────────────────┐
         │ ALWAYS: 200 OK                               │
         │ {                                            │
         │   status: "success",                         │
         │   order_id: "xxx"                            │
         │ }                                            │
         └──────────────────────────────────────────────┘
                                ↓
┌──────────────────────────────────────────────────────────────────────┐
│ PAYSTACK SERVERS                                                     │
│ - Received 200 OK                                                    │
│ - Won't retry webhook                                                │
│ - Webhook delivery marked successful ✓                               │
└──────────────────────────────────────────────────────────────────────┘
```

## 4. Idempotency - Duplicate Webhook Handling

```
First Webhook:
┌────────────────────────────────────────────────────────────────┐
│ POST /payments/webhook (ref_123456789)                        │
│ {event: "charge.success", data: {reference: "ref_123456789"}} │
└────────────────────────────────────────────────────────────────┘
                        ↓
        1. Verify signature ✓
        2. Parse event ✓
        3. Get order by reference ✓
        4. Order status == "pending" → UPDATE to "paid"
        5. Log: payment_confirmed
        6. Return 200 OK
                        ↓
        Order now marked as PAID in database


Second Webhook (Paystack retried):
┌────────────────────────────────────────────────────────────────┐
│ POST /payments/webhook (ref_123456789)                        │
│ {event: "charge.success", data: {reference: "ref_123456789"}} │
└────────────────────────────────────────────────────────────────┘
                        ↓
        1. Verify signature ✓
        2. Parse event ✓
        3. Get order by reference ✓
        4. Order status == "paid" → SKIP UPDATE (idempotent!)
        5. Log: already_paid
        6. Return 200 OK
                        ↓
        Order remains PAID (no duplicate charge risk)
```

## 5. Security Flow - Signature Verification

```
Paystack Server generates:
┌─────────────────────────────────────────────────────────────┐
│ HMAC-SHA512 Calculation:                                    │
│ 1. Get webhook_secret from Paystack dashboard               │
│ 2. Get payload body (raw bytes)                             │
│ 3. Calculate: hmac = SHA512(webhook_secret, payload)        │
│ 4. Send in header: x-paystack-signature: <hmac>             │
└─────────────────────────────────────────────────────────────┘
                        ↓
        Backend receives webhook with signature header
                        ↓
Backend verifies:
┌─────────────────────────────────────────────────────────────┐
│ 1. Read raw_body (bytes) from request                       │
│ 2. Recalculate: hmac = SHA512(webhook_secret, raw_body)     │
│ 3. Compare: calculated_hmac == received_signature?          │
│                                                             │
│ If YES: ✓ Webhook is genuine, process it                   │
│ If NO:  ✗ Invalid signature, reject silently               │
│         (Return 200 OK but don't process)                   │
└─────────────────────────────────────────────────────────────┘

Result: Only valid webhooks from Paystack are processed
        Prevents unauthorized payment confirmation attempts
```

## 6. Error Flow - Invalid Signature

```
Attacker attempts to forge webhook:
┌────────────────────────────────────────────────┐
│ POST /payments/webhook                         │
│ Header: x-paystack-signature: "fake_signature" │
│ Body: {event: "charge.success", ...}           │
└────────────────────────────────────────────────┘
                        ↓
        Backend reads raw body, webhook secret
                        ↓
        Calculate HMAC-SHA512
                        ↓
        Compare: calculated ≠ received
                        ↓
        ❌ Signature mismatch!
                        ↓
        Log: "webhook_invalid_signature" (warning)
        DO NOT update order status
        DO NOT process payment
                        ↓
        Return 200 OK (to Paystack)
        (200 signals: "OK, stop retrying")
                        ↓
Backend is secure ✓
Order is NOT marked as paid ✓
No damage from forgery ✓
```

## 7. Error Recovery - Timeout

```
User initiates payment → Backend calls Paystack API
                            ↓
                    Connection times out
                    (30 second timeout)
                            ↓
                    Exception raised
                            ↓
                    Caught by error handler
                            ↓
                    Log: "paystack_api_error"
                            ↓
                    Return to user: 
                    {error: "Paystack API error: timeout"}
                            ↓
                    User sees message
                            ↓
                    Order remains PENDING
                            ↓
                    User can retry later
                            ↓
                    Safe - no double payment risk
```

## State Transitions

```
                    ┌─────────────────────┐
                    │      PENDING        │ (Order created)
                    │                     │
                    └──────────┬──────────┘
                         │
                  (User clicks Pay)
                         │
                         ↓
    POST /payments/initialize
    (Get checkout URL)
                         │
                         ↓
                    ┌─────────────────────┐
                    │      PENDING        │ (Payment reference stored)
                    │                     │
                    └──────────┬──────────┘
                         │
        (User completes payment on Paystack)
        (Paystack sends webhook charge.success)
                         │
                         ↓
                  POST /payments/webhook
                         │
                         ↓
                    ┌─────────────────────┐
                    │      PAID           │ ✓ Order ready for fulfillment
                    │                     │
                    └─────────────────────┘

        Alternative: User cancels or payment fails
                         │
                         ↓
                  POST /payments/webhook
                  (charge.failed event)
                         │
                         ↓
                    ┌─────────────────────┐
                    │      FAILED         │ ✗ User can retry
                    │                     │
                    └─────────────────────┘
```

## Summary

1. **Initialize** - Start payment, get checkout URL
2. **User Redirect** - Paystack handles payment details
3. **Webhook** - Paystack confirms to backend (authoritative ✓)
4. **Verify** - User can check status after returning
5. **Idempotency** - Multiple webhooks safe
6. **Security** - HMAC-SHA512 verified
7. **Error Recovery** - Graceful handling, order safe

The backend NEVER trusts client callbacks - only Paystack webhooks are authoritative.
