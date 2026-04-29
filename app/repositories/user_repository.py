"""User Repository — admin read-only operations."""
from app.core.exceptions import NotFoundError
from app.core.supabase import get_supabase_admin_client

TABLE        = "users"
SAFE_COLUMNS = "id, email, role, created_at"


class UserRepository:
    def __init__(self):
        self.db = get_supabase_admin_client()

    def get_all(self, page=1, page_size=20):
        offset = (page - 1) * page_size
        total  = (self.db.table(TABLE).select("id", count="exact").execute().count or 0)
        items  = (
            self.db.table(TABLE)
            .select(SAFE_COLUMNS)
            .order("created_at", desc=True)
            .range(offset, offset + page_size - 1)
            .execute()
            .data or []
        )
        return items, total

    def get_by_id(self, user_id: str) -> dict:
        res = self.db.table(TABLE).select(SAFE_COLUMNS).eq("id", user_id).single().execute()
        if not res.data:
            raise NotFoundError(f"User {user_id} not found")
        return res.data