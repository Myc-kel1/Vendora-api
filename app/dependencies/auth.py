"""
FastAPI Auth Dependencies.

Two injectable dependencies for protecting routes:

  get_current_user  → validates JWT, returns CurrentUser
                      use on any route that requires login

  get_current_admin → validates JWT AND asserts role='admin'
                      use on all /admin/* routes

Usage in route handlers:
─────────────────────────────────────────────────────────────────────
    # Any authenticated user
    @router.get("/cart")
    def get_cart(user: CurrentUser = Depends(get_current_user)):
        return service.get_cart(user.id)

    # Admin only — returns 403 for regular users
    @router.post("/admin/products")
    def create_product(admin: CurrentUser = Depends(get_current_admin)):
        return service.create_product(...)

    # When you only need auth enforced but don't use the user object
    @router.get("/categories")
    def list_categories(_: CurrentUser = Depends(get_current_user)):
        return service.list_categories()
─────────────────────────────────────────────────────────────────────

Token format expected:
    Authorization: Bearer <supabase-access-token>

Error responses:
    401 AuthenticationError — missing/invalid/expired token
    403 ForbiddenError      — valid token but role ≠ 'admin'
"""
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.exceptions import AuthenticationError, ForbiddenError
from app.core.security import decode_jwt, extract_email, extract_role, extract_user_id
from app.schemas.user import CurrentUser

# HTTPBearer extracts the token from "Authorization: Bearer <token>"
# auto_error=False so we can raise our own typed AuthenticationError
# instead of FastAPI's generic 403
bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> CurrentUser:
    """
    Validate the Bearer JWT and return the authenticated user.

    Steps:
    1. Check that the Authorization header is present
    2. Decode and verify the JWT signature + expiry
    3. Extract user_id (sub), email, and role from the payload
    4. Return a CurrentUser instance

    Raises:
        AuthenticationError (401): if header is missing, token is
        invalid, malformed, or expired.
    """
    if not credentials:
        raise AuthenticationError(
            "Authorization header missing. "
            "Include 'Authorization: Bearer <token>' in your request."
        )

    token = credentials.credentials
    payload = decode_jwt(token)

    return CurrentUser(
        id=extract_user_id(payload),
        email=extract_email(payload),
        role=extract_role(payload),
    )


async def get_current_admin(
    current_user: CurrentUser = Depends(get_current_user),
) -> CurrentUser:
    """
    Validate the JWT and assert the user holds the 'admin' role.

    Chains off get_current_user — authentication is always checked
    first. If the user is valid but not an admin, ForbiddenError is
    raised before the route handler is ever called.

    Raises:
        AuthenticationError (401): invalid/missing token (from get_current_user)
        ForbiddenError (403): valid token but role is not 'admin'
    """
    if current_user.role != "admin":
        raise ForbiddenError(
            "This endpoint requires admin privileges. "
            "Your account does not have the required role."
        )
    return current_user
