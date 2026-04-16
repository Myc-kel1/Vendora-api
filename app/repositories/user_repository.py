"""
User Repository.

Admin-only database operations on the public.users table.

This table is a mirror of auth.users (Supabase's internal auth table).
It is populated automatically when a user signs up via the
handle_new_user() DB trigger (migration 002).

All operations use the service role client — RLS is intentionally
bypassed here because this repository is only called from admin-guarded
routes. The route-level get_current_admin dependency enforces that only
admins can reach any code that instantiates this repository.

Available operations:
  get_all(page, page_size)  → paginated user list, newest first
  get_by_id(user_id)        → single user profile or NotFoundError

Role promotion (user → admin) is intentionally NOT in this repository.
It is done via the promote_to_admin() SQL function (migration 002) to
prevent accidental privilege escalation through the HTTP API.
"""
from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.core.supabase import get_supabase_admin_client

logger = get_logger(__name__)

TABLE = "users"

# Fields returned to the admin — never expose password hashes or internal fields
SAFE_COLUMNS = "id, email, role, created_at"


class UserRepository:
    def __init__(self):
        self.db = get_supabase_admin_client()

    def get_all(self, page: int = 1, page_size: int = 20) -> tuple[list[dict], int]:
        """
        Return a paginated list of all registered users, newest first.

        Returns:
            tuple of (list of user dicts, total count)

        The total count reflects all users, not just the current page —
        clients use this to render pagination controls.
        """
        offset = (page - 1) * page_size

        # Count all users (separate query — Supabase requires this)
        count_res = (
            self.db.table(TABLE)
            .select("id", count="exact")
            .execute()
        )
        total = count_res.count or 0

        # Fetch the requested page
        res = (
            self.db.table(TABLE)
            .select(SAFE_COLUMNS)
            .order("created_at", desc=True)
            .range(offset, offset + page_size - 1)
            .execute()
        )
        return res.data or [], total

    def get_by_id(self, user_id: str) -> dict:
        """
        Fetch a single user profile by UUID.

        Raises:
            NotFoundError: if no user with this ID exists in public.users.
                           This can happen if the auth trigger hasn't fired
                           yet or if the user was deleted from auth.users.
        """
        res = (
            self.db.table(TABLE)
            .select(SAFE_COLUMNS)
            .eq("id", user_id)
            .single()
            .execute()
        )
        if not res.data:
            raise NotFoundError(f"User {user_id} not found")
        return res.data
