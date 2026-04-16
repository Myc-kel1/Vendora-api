"""
Supabase Client Factory.

Provides two distinct Supabase clients with different privilege levels:

┌─────────────────────────────┬──────────────────────────────────────────────┐
│ Client                      │ When to use                                  │
├─────────────────────────────┼──────────────────────────────────────────────┤
│ get_supabase_client()       │ Standard user-scoped queries where RLS       │
│ (anon key)                  │ enforcement is desired. Not currently used    │
│                             │ in this backend because we manage scoping     │
│                             │ at the service layer, but available for       │
│                             │ future user-authenticated Supabase calls.     │
├─────────────────────────────┼──────────────────────────────────────────────┤
│ get_supabase_admin_client() │ All backend operations — repositories,        │
│ (service role key)          │ webhooks, order creation, stock deduction.    │
│                             │ Bypasses RLS. NEVER expose this client or     │
│                             │ its key to the frontend/client side.          │
└─────────────────────────────┴──────────────────────────────────────────────┘

Both clients are cached with @lru_cache — only one connection object
is created per process for each key type.

Security rules:
  - Service role key must never be sent to the client or logged
  - Only call get_supabase_admin_client() from repository/service layers
  - Route handlers must never directly instantiate a Supabase client
"""
from functools import lru_cache

from supabase import Client, create_client

from app.core.config import get_settings


@lru_cache
def get_supabase_client() -> Client:
    """
    Anon/public Supabase client.

    Uses the anon key — RLS policies are enforced for this client.
    Suitable for operations that should respect row-level access control.
    """
    settings = get_settings()
    return create_client(
        supabase_url=settings.supabase_url,
        supabase_key=settings.supabase_anon_key,
    )


@lru_cache
def get_supabase_admin_client() -> Client:
    """
    Service role Supabase client — elevated privileges.

    Uses the service_role key, which bypasses all RLS policies.
    This is intentional — our backend enforces access control at the
    service/dependency layer (JWT verification + role checks).
    The DB's RLS acts as a second line of defence for direct DB access,
    but our backend operations need to work across all rows.

    SECURITY: Never pass this client or its underlying key to any
    code path that handles untrusted user input directly.
    """
    settings = get_settings()
    return create_client(
        supabase_url=settings.supabase_url,
        supabase_key=settings.supabase_service_role_key,
    )
