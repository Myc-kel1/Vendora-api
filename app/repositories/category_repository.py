"""
Category Repository.

All DB operations for the categories table.
Categories are admin-managed reference data used to organise products.
"""
from uuid import UUID

from app.core.exceptions import NotFoundError, ConflictError
from app.core.supabase import get_supabase_admin_client
from app.core.logging import get_logger

logger = get_logger(__name__)

TABLE = "categories"


class CategoryRepository:
    def __init__(self):
        self.db = get_supabase_admin_client()

    def get_all(self) -> list[dict]:
        """Fetch all categories ordered alphabetically."""
        res = (
            self.db.table(TABLE)
            .select("*")
            .order("name")
            .execute()
        )
        return res.data or []

    def get_by_id(self, category_id: UUID) -> dict:
        """Fetch a single category. Raises NotFoundError if missing."""
        res = (
            self.db.table(TABLE)
            .select("*")
            .eq("id", str(category_id))
            .single()
            .execute()
        )
        if not res.data:
            raise NotFoundError(f"Category {category_id} not found")
        return res.data

    def get_by_name(self, name: str) -> dict | None:
        """Look up a category by exact name (for duplicate check)."""
        res = (
            self.db.table(TABLE)
            .select("*")
            .eq("name", name)
            .limit(1)
            .execute()
        )
        return res.data[0] if res.data else None

    def create(self, name: str) -> dict:
        """Insert a new category. Raises ConflictError if name already exists."""
        existing = self.get_by_name(name)
        if existing:
            raise ConflictError(f"Category '{name}' already exists")
        res = self.db.table(TABLE).insert({"name": name}).execute()
        logger.info("category_created", name=name)
        return res.data[0]

    def update(self, category_id: UUID, name: str) -> dict:
        """Rename a category. Raises ConflictError if new name already exists."""
        existing = self.get_by_name(name)
        if existing and existing["id"] != str(category_id):
            raise ConflictError(f"Category '{name}' already exists")
        res = (
            self.db.table(TABLE)
            .update({"name": name})
            .eq("id", str(category_id))
            .execute()
        )
        if not res.data:
            raise NotFoundError(f"Category {category_id} not found")
        logger.info("category_updated", category_id=str(category_id), name=name)
        return res.data[0]

    def delete(self, category_id: UUID) -> None:
        """
        Delete a category. Supabase will SET NULL on products.category_id
        (via ON DELETE SET NULL FK constraint) — products are not deleted.
        """
        self.get_by_id(category_id)  # raises NotFoundError if missing
        self.db.table(TABLE).delete().eq("id", str(category_id)).execute()
        logger.info("category_deleted", category_id=str(category_id))
