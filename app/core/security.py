"""
JWT Security Utilities.

Supabase issues JWTs signed with ES256 (using Supabase's private key).
This module verifies those tokens by fetching Supabase's public key
from their JWKS endpoint.

Token structure (Supabase-specific):
  {
    "sub": "<user-uuid>",           ← user ID
    "email": "user@example.com",
    "role": "authenticated",        ← Supabase's role (not ours)
    "app_metadata": {
      "role": "user" | "admin"      ← OUR custom role (set via trigger)
    },
    "exp": <unix-timestamp>,
    "aud": "authenticated"
  }

IMPORTANT: Role is read from app_metadata.role (set server-side via
the sync_role_to_auth_metadata() DB trigger). Never read from
user_metadata — users can edit that themselves.

Public surface:
  decode_jwt(token)            → validated payload dict
  extract_user_id(payload)     → str UUID
  extract_role(payload)        → "user" | "admin"
  require_role(payload, role)  → None or raises ForbiddenError
"""
from datetime import datetime, timezone
from functools import lru_cache
from jose import jwt
import httpx
from jose import JWTError, jwt
import requests

from app.core.config import get_settings
from app.core.exceptions import AuthenticationError, ForbiddenError


@lru_cache(maxsize=1)
def _get_supabase_public_key():
    """
    Fetch Supabase's public key from the JWKS endpoint.
    
    Cached to avoid repeated network calls during request handling.
    
    Returns:
        The public key object for verifying ES256 tokens
        
    Raises:
        AuthenticationError: if unable to fetch the key
    """
    settings = get_settings()
    jwks_url = f"{settings.supabase_url}/auth/v1/.well-known/jwks.json"
    jwks = requests.get(jwks_url).json()

      # Supabase usually returns 1 active key
    key_data = jwks["keys"][0]

    return key_data


def decode_jwt(token: str):
    jwks = _get_supabase_public_key()

    payload = jwt.decode(
        token,
        jwks,
        algorithms=["ES256"],   # Supabase uses ES256
        audience="authenticated"
    )

    return payload


def extract_user_id(payload: dict) -> str:
    """
    Extract the user's UUID from the 'sub' claim of a decoded JWT.

    Raises:
        AuthenticationError: if the 'sub' claim is missing.
    """
    user_id = payload.get("sub")
    if not user_id:
        raise AuthenticationError("Token is missing the subject (sub) claim")
    return user_id


def extract_role(payload: dict) -> str:
    """
    Extract the user's custom application role from app_metadata.

    Reads from payload["app_metadata"]["role"].
    Defaults to "user" if the key is absent (new users before the
    auth trigger has fired, or if app_metadata is empty).

    Never reads from user_metadata — that field is user-editable.
    app_metadata is set server-side only (via our DB trigger).
    """
    app_metadata = payload.get("app_metadata") or {}
    return app_metadata.get("role", "user")


def extract_email(payload: dict) -> str:
    """Extract the user's email from the JWT payload."""
    return payload.get("email", "")


def require_role(payload: dict, required_role: str) -> None:
    """
    Assert that the decoded JWT payload carries the required role.

    Used as a lightweight guard in service-layer code.
    For route-level enforcement, prefer the get_current_admin
    dependency in app/dependencies/auth.py.

    Raises:
        ForbiddenError: if the token's role does not match required_role.
    """
    role = extract_role(payload)
    if role != required_role:
        raise ForbiddenError(
            f"This action requires role='{required_role}'. "
            f"Your token has role='{role}'."
        )
