"""Category Repository."""
from uuid import UUID
from app.core.exceptions import ConflictError, NotFoundError
from app.core.logging import get_logger
from app.core.supabase import get_supabase_admin_client

logger = get_logger(__name__)
TABLE  = "categories"


class CategoryRepository:
    def __init__(self):
        self.db = get_supabase_admin_client()

    def get_all(self) -> list[dict]:
        return self.db.table(TABLE).select("*").order("name").execute().data or []

    def get_by_id(self, cat_id: UUID) -> dict:
        res = self.db.table(TABLE).select("*").eq("id", str(cat_id)).single().execute()
        if not res.data:
            raise NotFoundError(f"Category {cat_id} not found")
        return res.data

    def get_by_name(self, name: str) -> dict | None:
        res = self.db.table(TABLE).select("*").eq("name", name).limit(1).execute()
        return res.data[0] if res.data else None

    def create(self, name: str) -> dict:
        if self.get_by_name(name):
            raise ConflictError(f"Category '{name}' already exists")
        res = self.db.table(TABLE).insert({"name": name}).execute()
        return res.data[0]

    def update(self, cat_id: UUID, name: str) -> dict:
        existing = self.get_by_name(name)
        if existing and existing["id"] != str(cat_id):
            raise ConflictError(f"Category '{name}' already exists")
        res = self.db.table(TABLE).update({"name": name}).eq("id", str(cat_id)).execute()
        if not res.data:
            raise NotFoundError(f"Category {cat_id} not found")
        return res.data[0]

    def delete(self, cat_id: UUID) -> None:
        self.get_by_id(cat_id)  # raises NotFoundError if missing
        self.db.table(TABLE).delete().eq("id", str(cat_id)).execute()