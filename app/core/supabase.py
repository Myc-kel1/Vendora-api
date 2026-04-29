"""
Supabase client factory.

Two clients are provided:
  get_supabase_client()       → anon key (respects RLS)
  get_supabase_admin_client() → service role key (bypasses RLS)

The admin client is used by all repository/service layers because our
access control is enforced at the FastAPI dependency layer (JWT + role checks).
The DB's RLS acts as a second line of defence for direct DB access.

NEVER pass the admin client or service role key to client-side code.
"""
from functools import lru_cache
from supabase import Client, create_client
from app.core.config import get_settings


@lru_cache
def get_supabase_client() -> Client:
    """Anon client — RLS enforced."""
    s = get_settings()
    return create_client(s.supabase_url, s.supabase_anon_key)


@lru_cache
def get_supabase_admin_client() -> Client:
    """Service role client — RLS bypassed. Backend use only."""
    s = get_settings()
    return create_client(s.supabase_url, s.supabase_service_role_key)