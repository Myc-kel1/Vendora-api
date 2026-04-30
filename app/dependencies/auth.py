"""
FastAPI authentication and authorization dependencies.
"""

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.exceptions import AuthenticationError, ForbiddenError
from app.core.security import (
    decode_jwt,
    extract_email,
    extract_role,
    extract_user_id,
)
from app.schemas.user import CurrentUser


# We handle errors manually → consistent 401 responses
bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> CurrentUser:
    """
    Validate the Bearer JWT and return the authenticated user.
    """

    if not credentials:
        raise AuthenticationError(
            "Authorization header missing. "
            "Send: Authorization: Bearer <your_supabase_access_token>"
        )

    # ✅ FIX: decode_jwt is async → MUST await
    payload = await decode_jwt(credentials.credentials)

    # Extra safety: ensure payload is dict
    if not isinstance(payload, dict):
        raise AuthenticationError("Invalid token payload")

    return CurrentUser(
        id=extract_user_id(payload),
        email=extract_email(payload),
        role=extract_role(payload),
    )


async def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> CurrentUser | None:
    """
    Optional authentication (for public endpoints).
    """

    if not credentials:
        return None

    # ✅ FIX: await here too
    payload = await decode_jwt(credentials.credentials)

    if not isinstance(payload, dict):
        raise AuthenticationError("Invalid token payload")

    return CurrentUser(
        id=extract_user_id(payload),
        email=extract_email(payload),
        role=extract_role(payload),
    )


async def get_current_admin(
    current_user: CurrentUser = Depends(get_current_user),
) -> CurrentUser:
    """
    Require admin privileges.
    """

    # ✅ strict role check
    if current_user.role != "admin":
        raise ForbiddenError(
            "This endpoint requires admin privileges. "
            f"Your account role is: {current_user.role}"
        )

    return current_user