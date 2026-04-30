from jose import JWTError, jwt
import httpx
from functools import lru_cache

from app.core.config import get_settings
from app.core.exceptions import AuthenticationError

ALGORITHMS = ["RS256"]


# -----------------------------
# JWKS CACHE
# -----------------------------
_jwks_cache = None


async def get_jwks():
    """
    Fetch Supabase JWKS (public keys).
    This endpoint is public — no auth required.
    """
    global _jwks_cache

    if _jwks_cache:
        return _jwks_cache

    settings = get_settings()

    url = f"{settings.supabase_url}/auth/v1/keys"

    async with httpx.AsyncClient(timeout=5.0) as client:
        res = await client.get(url)

        if res.status_code != 200:
            raise AuthenticationError(
                f"Failed to fetch JWKS: {res.status_code} {res.text}"
            )

        _jwks_cache = res.json()
        return _jwks_cache


# -----------------------------
# GET SIGNING KEY
# -----------------------------
def get_public_key(jwks: dict, kid: str) -> str:
    """
    Extract correct RSA public key from JWKS using kid.
    """
    for key in jwks.get("keys", []):
        if key.get("kid") == kid:
            return key

    raise AuthenticationError("Invalid token key ID (kid not found)")


# -----------------------------
# DECODE JWT
# -----------------------------
async def decode_jwt(token: str) -> dict:
    """
    Verify Supabase JWT using RS256 + JWKS.
    """
    settings = get_settings()

    try:
        # 1. Read token header (NO verification yet)
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")

        if not kid:
            raise AuthenticationError("Token missing kid header")

        # 2. Fetch JWKS
        jwks = await get_jwks()

        # 3. Get correct key
        public_key = get_public_key(jwks, kid)

        # 4. Verify token
        payload = jwt.decode(
            token,
            public_key,
            algorithms=ALGORITHMS,
            audience="authenticated",
            issuer=f"{settings.supabase_url}/auth/v1",
        )

        return payload

    except JWTError as exc:
        raise AuthenticationError(f"Invalid or expired token: {exc}")


# -----------------------------
# EXTRACTORS (safe)
# -----------------------------
def extract_user_id(payload: dict) -> str:
    uid = payload.get("sub")
    if not uid:
        raise AuthenticationError("Token missing sub")
    return uid


def extract_email(payload: dict) -> str:
    return payload.get("email", "")


def extract_role(payload: dict) -> str:
    return (payload.get("app_metadata") or {}).get("role", "user")