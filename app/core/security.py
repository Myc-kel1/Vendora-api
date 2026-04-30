"""
JWT verification — Supabase RS256 tokens (modern standard).

Token structure (Supabase-specific):
  sub           → user UUID  (the user's ID)
  email         → user email
  app_metadata  → { "role": "user" | "admin" }  — set SERVER-SIDE only, tamper-proof
  exp           → Unix expiry timestamp
  aud           → "authenticated"
  iss           → https://<project>.supabase.co/auth/v1

We verify tokens using Supabase JWKS (public keys).
This is required for RS256 (asymmetric signing).

We read role from app_metadata ONLY, never from user_metadata.
user_metadata is editable by the user — never trust it for authorization.
"""

from jose import JWTError, jwt
import httpx

from app.core.config import get_settings
from app.core.exceptions import AuthenticationError

# Supabase uses RS256 for modern projects
ALGORITHMS = ["RS256"]

# Simple in-memory cache for JWKS
_JWKS_CACHE: dict | None = None


async def _get_jwks() -> dict:
    """
    Fetch and cache Supabase JWKS (public keys).
    """
    global _JWKS_CACHE

    if _JWKS_CACHE:
        return _JWKS_CACHE

    settings = get_settings()
    url = f"{settings.supabase_url}/auth/v1/keys"

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            _JWKS_CACHE = response.json()
            return _JWKS_CACHE

    except Exception as exc:
        raise AuthenticationError(f"Failed to fetch JWKS: {exc}")


async def decode_jwt(token: str) -> dict:
    """
    Decode and cryptographically verify a Supabase JWT (RS256).

    Raises AuthenticationError if:
      - Token is malformed or tampered
      - Signature is invalid
      - Token is expired (handled by python-jose)
      - Issuer or audience is invalid
    """
    settings = get_settings()

    try:
        jwks = await _get_jwks()

        payload = jwt.decode(
            token,
            jwks,
            algorithms=ALGORITHMS,
            audience="authenticated",
            issuer=f"{settings.supabase_url}/auth/v1",
        )

        return payload

    except JWTError as exc:
        raise AuthenticationError(f"Invalid or expired token: {exc}")


def extract_user_id(payload: dict) -> str:
    """
    Extract user UUID from the 'sub' claim.
    """
    uid = payload.get("sub")
    if not uid:
        raise AuthenticationError("Token missing subject (sub) claim")
    return uid


def extract_email(payload: dict) -> str:
    """
    Extract user email.
    """
    return payload.get("email", "")


def extract_role(payload: dict) -> str:
    """
    Extract application role from app_metadata.role.

    Defaults to 'user' if:
      - app_metadata is absent
      - role key is not present

    SECURITY:
    app_metadata is server-controlled (Supabase service role / DB triggers).
    Users cannot modify it via client SDK.
    """
    return (payload.get("app_metadata") or {}).get("role", "user")