# Image Upload & Auth Best Practices Implementation

## Overview
This document describes the improvements made to support product image uploads during creation and implement security best practices across the authentication system.

---

## 1. Product Image Upload Feature

### 1.1 Creating Products with Images

**Endpoint**: `POST /admin/products`

#### Request Format (Form-Data)
```bash
curl -X POST "http://localhost:8000/admin/products" \
  -H "Authorization: Bearer {token}" \
  -F "name=Premium Laptop" \
  -F "description=High-performance laptop with 16GB RAM" \
  -F "price=999.99" \
  -F "stock=50" \
  -F "category_id=550e8400-e29b-41d4-a716-446655440000" \
  -F "file=@/path/to/image.jpg"
```

#### Request Parameters
- **name** (string, required): Product name (1-255 characters)
- **description** (string, required): Product description
- **price** (float, required): Product price (must be > 0)
- **stock** (integer, required): Initial stock quantity (≥ 0)
- **category_id** (UUID, optional): Product category
- **file** (file, optional): Product image file

#### Supported Image Formats
- JPEG/JPG
- PNG
- WebP
- GIF

#### Constraints
- **Maximum file size**: 5 MB
- **Content-Type validation**: Automatic validation of image format

#### Response (201 Created)
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Premium Laptop",
  "description": "High-performance laptop with 16GB RAM",
  "price": 999.99,
  "stock": 50,
  "category_id": "550e8400-e29b-41d4-a716-446655440000",
  "image_url": "https://storage.example.com/product-images/550e8400-e29b-41d4-a716-446655440000/...",
  "is_active": true,
  "created_by": "admin-uuid",
  "created_at": "2026-04-29T10:30:00Z",
  "updated_at": "2026-04-29T10:30:00Z"
}
```

### 1.2 Updating Product Images

**Endpoint**: `POST /admin/products/{product_id}/image`

Upload or replace image for existing product:
```bash
curl -X POST "http://localhost:8000/admin/products/{product_id}/image" \
  -H "Authorization: Bearer {token}" \
  -F "file=@/path/to/image.jpg"
```

### 1.3 Removing Product Images

**Endpoint**: `DELETE /admin/products/{product_id}/image`

Remove image from product:
```bash
curl -X DELETE "http://localhost:8000/admin/products/{product_id}/image" \
  -H "Authorization: Bearer {token}"
```

---

## 2. Authentication & Authorization Best Practices

### 2.1 Security Architecture

The authentication system implements a multi-layered security model:

```
┌─────────────────────────────────────────────┐
│           HTTP Request                      │
└────────────────────┬────────────────────────┘
                     │
        ┌────────────▼────────────┐
        │  HTTPBearer Middleware  │
        │  (Extract Bearer token) │
        └────────────┬────────────┘
                     │
        ┌────────────▼────────────────────────┐
        │  decode_jwt(token)                  │
        │  ✓ Fetch JWKS public key (cached)   │
        │  ✓ Verify signature (ES256)         │
        │  ✓ Validate expiration              │
        │  ✓ Validate audience claim          │
        └────────────┬────────────────────────┘
                     │
        ┌────────────▼────────────────────────┐
        │  validate_token_claims(payload)     │
        │  ✓ Check required claims present    │
        │  ✓ Validate claim format            │
        └────────────┬────────────────────────┘
                     │
        ┌────────────▼────────────────────────┐
        │  Extract user info                  │
        │  - user_id (sub claim)              │
        │  - email                            │
        │  - role (app_metadata.role)         │
        └────────────┬────────────────────────┘
                     │
        ┌────────────▼────────────────────────┐
        │  Authorization Check (if required)  │
        │  - Check role ≠ "admin" → 403       │
        └────────────┬────────────────────────┘
                     │
        ┌────────────▼────────────────────────┐
        │  Request Handler / Route            │
        │  (User object available)            │
        └─────────────────────────────────────┘
```

### 2.2 JWT Token Structure (Supabase)

```json
{
  "sub": "550e8400-e29b-41d4-a716-446655440000",  // User ID
  "email": "admin@example.com",
  "email_confirmed_at": "2026-04-29T10:00:00Z",
  "app_metadata": {
    "role": "admin"  // Our custom role (set server-side)
  },
  "user_metadata": {
    // User-editable (never trust for auth)
  },
  "aud": "authenticated",
  "exp": 1719676800,  // Expiration timestamp
  "iat": 1719673200,  // Issued at
  "jti": "..."
}
```

**IMPORTANT**: Role is read from `app_metadata.role`, which is set server-side via database trigger. Never read from `user_metadata` (users can edit it).

### 2.3 Error Responses

#### 401 Unauthorized (Authentication Failed)
```json
{
  "error": "Token has expired. Please sign in again."
}
```

Scenarios:
- Missing Authorization header
- Invalid token format
- Invalid token signature
- Expired token
- Invalid audience claim
- Missing required claims

#### 403 Forbidden (Authorization Failed)
```json
{
  "error": "This endpoint requires admin privileges. Your account does not have the required role."
}
```

Scenarios:
- Valid token but user role ≠ 'admin'
- User lacks required permissions

### 2.4 Security Best Practices Implemented

#### Token Validation
```python
# ✓ Always verify JWT signature via JWKS
# ✓ Check token expiration
# ✓ Validate audience claim
# ✓ Verify all required claims present
# ✓ Handle JWT decode errors gracefully
```

#### Error Handling
```python
# ✓ Distinguish between authentication (401) and authorization (403)
# ✓ Provide clear error messages
# ✓ Never leak token details in error messages
# ✓ Log security events for audit trail
```

#### Network Security
```python
# ✓ CORS configured with explicit origins (never use *)
# ✓ Only allow required HTTP methods
# ✓ Restrict allowed headers
# ✓ Add security headers to all responses:
#   - X-Content-Type-Options: nosniff (prevent MIME sniffing)
#   - X-XSS-Protection: 1; mode=block (XSS protection)
#   - X-Frame-Options: DENY (clickjacking protection)
#   - Referrer-Policy: strict-origin-when-cross-origin
#   - HSTS: max-age=31536000 (in production)
#   - Content-Security-Policy (restrict resource loading)
```

#### Key Caching
```python
# ✓ JWKS public key cached (LRU cache, maxsize=1)
# ✓ Avoids repeated network calls to JWKS endpoint
# ✓ Reduces rate limiting issues
# ✓ Improves performance
```

#### Logging & Audit Trail
```python
# ✓ Auth events logged for security monitoring
# ✓ Failed login attempts tracked
# ✓ Permission denied events recorded
# ✓ Admin actions audited
# ✓ Never log sensitive data (tokens, passwords)
```

---

## 3. Auth Event Logging

All authentication and authorization events are logged for security auditing.

### 3.1 Event Types

```python
from app.core.auth_audit import AuthEventType

# Authentication events
USER_LOGIN_SUCCESS
USER_LOGIN_FAILED
TOKEN_REFRESH
TOKEN_VALIDATION_FAILED
TOKEN_EXPIRED

# Authorization events
PERMISSION_DENIED
ADMIN_ACCESS_DENIED

# Admin events
ADMIN_LOGIN
ADMIN_ACTION
ROLE_CHANGED

# Security events
INVALID_CREDENTIALS
SUSPICIOUS_ACTIVITY
```

### 3.2 Logging Failed Auth Attempts

```python
from app.core.auth_audit import log_auth_event, AuthEventType

log_auth_event(
    event_type=AuthEventType.TOKEN_VALIDATION_FAILED,
    email="user@example.com",
    ip_address="192.168.1.1",
    success=False,
    details="Token signature invalid"
)
```

### 3.3 Logging Admin Actions

```python
from app.core.auth_audit import log_admin_action

log_admin_action(
    admin_id="admin-uuid",
    action="create",
    resource="product",
    resource_id="product-uuid",
    changes={"name": "Product Name", "price": 99.99},
    success=True
)
```

---

## 4. Role-Based Access Control (RBAC)

### 4.1 Using get_current_admin

```python
from fastapi import APIRouter, Depends
from app.dependencies.auth import get_current_admin
from app.schemas.user import CurrentUser

router = APIRouter(prefix="/admin", tags=["Admin"])

@router.post("/products")
def create_product(
    admin: CurrentUser = Depends(get_current_admin),
    service: ProductService = Depends(ProductService),
):
    # Only admin users can reach here
    # admin.id, admin.email, admin.role are available
    return service.create_product(...)
```

### 4.2 Using get_current_user (for regular users)

```python
@router.get("/cart")
def get_cart(
    user: CurrentUser = Depends(get_current_user),
    service: CartService = Depends(CartService),
):
    # Any authenticated user can reach here
    return service.get_cart(user.id)
```

### 4.3 CurrentUser Model

```python
class CurrentUser(BaseModel):
    id: str          # UUID of the user
    email: str       # User email address
    role: str        # "user" or "admin"
```

---

## 5. Configuration

### 5.1 CORS Settings

Configure in `app/core/config.py`:

```python
CORS_ORIGINS = [
    "http://localhost:3000",    # React dev
    "http://localhost:5173",    # Vite dev
    "https://example.com",      # Production
]

# In production, always specify exact origins
# Never use ["*"] with allow_credentials=True
```

### 5.2 Security Headers (Production)

Automatically enabled in production mode:
- HSTS: Forces HTTPS-only communication
- CSP: Restricts where resources can be loaded from
- X-Frame-Options: Prevents clickjacking attacks

---

## 6. Common Issues & Troubleshooting

### Issue: "Token is expired"
**Solution**: Refresh token with Supabase auth system. Tokens typically expire after 1 hour.

### Issue: "Invalid token signature"
**Solution**: Ensure token is from authorized Supabase instance. Check SUPABASE_URL is correct.

### Issue: "This endpoint requires admin privileges"
**Solution**: User account doesn't have admin role. Check user's app_metadata.role in Supabase database.

### Issue: "Authorization header missing"
**Solution**: Include Authorization header: `Authorization: Bearer <token>`

### Issue: "File exceeds the 5 MB size limit"
**Solution**: Compress or resize image before upload. Maximum size is 5 MB.

---

## 7. Testing Auth Endpoints

### Test with curl

```bash
# Get admin token (from your auth system)
TOKEN="your_admin_token_here"

# Test creating product with image
curl -X POST "http://localhost:8000/admin/products" \
  -H "Authorization: Bearer $TOKEN" \
  -F "name=Test Product" \
  -F "description=Test Description" \
  -F "price=99.99" \
  -F "stock=10" \
  -F "file=@test-image.jpg"

# Test with invalid token (should return 401)
curl -X POST "http://localhost:8000/admin/products" \
  -H "Authorization: Bearer invalid_token" \
  -F "name=Test Product"

# Test as non-admin user (should return 403)
curl -X POST "http://localhost:8000/admin/products" \
  -H "Authorization: Bearer $USER_TOKEN" \
  -F "name=Test Product"
```

---

## 8. Files Modified

### Core Security
- `app/core/security.py`: Enhanced JWT validation with error handling
- `app/core/auth_audit.py`: New auth logging module
- `app/main.py`: Added security headers middleware

### Authentication
- `app/dependencies/auth.py`: Improved auth validation and logging

### API
- `app/api/admin/products.py`: Image upload during product creation
- `app/schemas/product.py`: Updated ProductCreate and ProductUpdate

---

## 9. Next Steps

Consider implementing:
1. **Rate limiting**: Limit failed login attempts (e.g., 5 attempts per 15 minutes)
2. **Refresh token rotation**: Automatically rotate refresh tokens on use
3. **Session management**: Track active sessions and allow logout
4. **Two-factor authentication**: Additional security for admin accounts
5. **IP whitelisting**: Restrict admin access to specific IP ranges
6. **Audit dashboard**: Real-time view of security events

---

**Version**: 1.0  
**Last Updated**: April 29, 2026  
**Author**: Admin Dev Team
