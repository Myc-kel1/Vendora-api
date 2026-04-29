"""
JWT verification — Supabase HS256 tokens.

Token structure (Supabase-specific):
  sub           → user UUID  (the user's ID)
  email         → user email
  app_metadata  → { "role": "user" | "admin" }  — set SERVER-SIDE only, tamper-proof
  exp           → Unix expiry timestamp
  aud           → "authenticated"

We read role from app_metadata ONLY, never from user_metadata.
user_metadata is editable by the user — never trust it for authorization.

python-jose validates signature AND expiry inside jwt.decode().
We do not duplicate the expiry check — that would imply we don't trust the library.
"""
from jose import JWTError, jwt
from app.core.config import get_settings
from app.core.exceptions import AuthenticationError

ALGORITHM = "HS256"


def decode_jwt(token: str) -> dict:
    """
    Decode and cryptographically verify a Supabase JWT.

    Raises AuthenticationError if:
      - Token is malformed or tampered
      - Signature does not match the project JWT secret
      - Token is expired (python-jose checks exp automatically)
    """
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=[ALGORITHM],
            # Supabase sets aud="authenticated" on all user tokens.
            # We skip audience validation here because we don't restrict
            # to a specific audience — Supabase handles that.
            options={"verify_aud": False},
        )
    except JWTError as exc:
        raise AuthenticationError(f"Invalid or expired token: {exc}")

    return payload


def extract_user_id(payload: dict) -> str:
    """
    Extract user UUID from the 'sub' claim.
    Raises AuthenticationError if claim is missing.
    """
    uid = payload.get("sub")
    if not uid:
        raise AuthenticationError("Token missing subject (sub) claim")
    return uid


def extract_email(payload: dict) -> str:
    return payload.get("email", "")


def extract_role(payload: dict) -> str:
    """
    Extract application role from app_metadata.role.

    Defaults to 'user' if:
      - app_metadata is absent (new user, trigger not yet fired)
      - role key is not present

    SECURITY: app_metadata is set exclusively by server-side DB triggers
    (sync_role_to_auth_metadata). Users cannot modify app_metadata through
    the Supabase client SDK — it requires service role access.
    """
    return (payload.get("app_metadata") or {}).get("role", "user")