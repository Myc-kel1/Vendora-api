"""Profile Repository — public.profiles table."""
from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.core.supabase import get_supabase_admin_client

logger        = get_logger(__name__)
PROFILE_TABLE = "profiles"
USER_TABLE    = "users"


class ProfileRepository:
    def __init__(self):
        self.db = get_supabase_admin_client()

    def get_by_user_id(self, user_id: str) -> dict:
        user_res = self.db.table(USER_TABLE).select("email, role, created_at").eq("id", user_id).single().execute()
        if not user_res.data:
            raise NotFoundError(f"User {user_id} not found")

        profile_res = self.db.table(PROFILE_TABLE).select("*").eq("id", user_id).single().execute()
        if not profile_res.data:
            # Auto-create profile row (backfill safety for pre-migration users)
            self.db.table(PROFILE_TABLE).insert({"id": user_id}).execute()
            profile_res = self.db.table(PROFILE_TABLE).select("*").eq("id", user_id).single().execute()

        return {
            **profile_res.data,
            "email":      user_res.data["email"],
            "role":       user_res.data["role"],
            "created_at": user_res.data["created_at"],
        }

    def upsert(self, user_id: str, data: dict) -> None:
        self.db.table(PROFILE_TABLE).upsert({"id": user_id, **data}, on_conflict="id").execute()
        logger.info("profile_updated", user_id=user_id)