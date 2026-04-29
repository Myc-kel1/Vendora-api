"""
FastAPI authentication and authorization dependencies.

Two dependencies:

  get_current_user  → validates JWT, returns CurrentUser
                       Use on any route that requires login.

  get_current_admin → validates JWT AND asserts role == 'admin'.
                       Use on all /admin/* routes.
                       Returns 403 for non-admins, 401 for missing/invalid token.

Why auto_error=False on HTTPBearer?
  FastAPI's default behavior returns a 403 when the header is missing.
  We use auto_error=False so we can return our own 401 AuthenticationError
  with a clear message, consistent with the rest of the error contract.

Token format expected:
  Authorization: Bearer <supabase_access_token>

The access token is a Supabase-issued JWT valid for 1 hour by default.
Refresh tokens should be handled client-side and are NOT sent to our API.
"""
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from app.core.exceptions import AuthenticationError, ForbiddenError
from app.core.security import decode_jwt, extract_email, extract_role, extract_user_id
from app.schemas.user import CurrentUser

# auto_error=False: we handle missing credentials ourselves with a 401
bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> CurrentUser:
    """
    Validate the Bearer JWT and return the authenticated user.

    Raises:
      AuthenticationError (401) — header missing, token invalid or expired
    """
    if not credentials:
        raise AuthenticationError(
            "Authorization header missing. "
            "Send: Authorization: Bearer <your_supabase_access_token>"
        )

    payload = decode_jwt(credentials.credentials)

    return CurrentUser(
        id=extract_user_id(payload),
        email=extract_email(payload),
        role=extract_role(payload),
    )


async def get_current_admin(
    current_user: CurrentUser = Depends(get_current_user),
) -> CurrentUser:
    """
    Assert the authenticated user has role='admin'.

    This chains from get_current_user — auth is always checked first.
    Admin role is set via: SELECT promote_to_admin('user-uuid');
    After promotion, the user must sign in again to get a fresh JWT
    that includes the updated app_metadata.role.

    Raises:
      AuthenticationError (401) — from get_current_user (invalid token)
      ForbiddenError (403)      — valid token but role is not 'admin'
    """
    if current_user.role != "admin":
        raise ForbiddenError(
            "This endpoint requires admin privileges. "
            "Your account role is: " + current_user.role
        )
    return current_user