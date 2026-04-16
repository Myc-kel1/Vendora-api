from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class CurrentUser(BaseModel):
    """Represents the authenticated user extracted from JWT."""
    id: str
    email: str
    role: Literal["user", "admin"] = "user"

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


class UserResponse(BaseModel):
    """Admin-facing user profile."""
    id: str
    email: str
    role: Literal["user", "admin"]
    created_at: datetime

    model_config = {"from_attributes": True}


class UserListResponse(BaseModel):
    items: list[UserResponse]
    total: int
