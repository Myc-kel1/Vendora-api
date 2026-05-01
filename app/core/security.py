"""
JWT validation via Supabase (ES256 compatible).

We do NOT manually verify JWT signatures.
Supabase handles validation via /auth/v1/user.

This works for:
- ES256 (your current setup)
- RS256 (future-proof)
- Any Supabase changes

We only trust:
- app_metadata.role (server-controlled)
"""

import httpx
from app.core.config import get_settings
from app.core.exceptions import AuthenticationError


async def decode_jwt(token: str) -> dict:
    """
    Validate Supabase JWT by calling Supabase Auth API.

    Raises AuthenticationError if token is invalid or expired.
    """
    settings = get_settings()

    url = f"{settings.supabase_url}/auth/v1/user"

    headers = {
        "Authorization": f"Bearer {token}",
        "apikey": settings.supabase_anon_key,
    }

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            res = await client.get(url, headers=headers)

            if res.status_code != 200:
                raise AuthenticationError("Invalid or expired token")

            return res.json()

    except Exception as exc:
        raise AuthenticationError(f"Auth validation failed: {exc}")


def extract_user_id(payload: dict) -> str:
    uid = payload.get("id")  # ⚠️ Supabase returns "id" not "sub" here
    if not uid:
        raise AuthenticationError("User ID missing from token")
    return uid


def extract_email(payload: dict) -> str:
    return payload.get("email", "")


def extract_role(payload: dict) -> str:
    return (payload.get("app_metadata") or {}).get("role", "user")