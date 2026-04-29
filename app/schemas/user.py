from datetime import date, datetime
from typing import Literal
from pydantic import BaseModel


class CurrentUser(BaseModel):
    """Authenticated user extracted from JWT. Not persisted."""
    id:    str
    email: str
    role:  Literal["user", "admin"] = "user"

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


class UserResponse(BaseModel):
    id:         str
    email:      str
    role:       Literal["user", "admin"]
    created_at: datetime
    model_config = {"from_attributes": True}


class UserListResponse(BaseModel):
    items: list[UserResponse]
    total: int


class ProfileResponse(BaseModel):
    """Full user profile — merges profiles + users tables."""
    id:            str
    email:         str
    role:          Literal["user", "admin"]
    first_name:    str | None = None
    last_name:     str | None = None
    phone:         str | None = None
    avatar_url:    str | None = None
    date_of_birth: date | None = None
    address_line1: str | None = None
    address_line2: str | None = None
    city:          str | None = None
    state:         str | None = None
    postal_code:   str | None = None
    country:       str | None = None
    created_at:    datetime
    updated_at:    datetime
    model_config = {"from_attributes": True}


class ProfileUpdate(BaseModel):
    """All fields optional — PATCH semantics, only send what changes."""
    first_name:    str | None = None
    last_name:     str | None = None
    phone:         str | None = None
    avatar_url:    str | None = None
    date_of_birth: date | None = None
    address_line1: str | None = None
    address_line2: str | None = None
    city:          str | None = None
    state:         str | None = None
    postal_code:   str | None = None
    country:       str | None = None