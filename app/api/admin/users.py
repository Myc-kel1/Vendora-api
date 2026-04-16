"""
Admin: User/Customer Management.

Read-only view of the customer base.
Role promotion is done via SQL (promote_to_admin function) to avoid
accidental privilege escalation through the API.
"""
from fastapi import APIRouter, Depends, Query

from app.dependencies.auth import get_current_admin
from app.repositories.user_repository import UserRepository
from app.schemas.user import CurrentUser, UserListResponse, UserResponse

router = APIRouter(prefix="/admin/users", tags=["Admin — Users"])


@router.get("", response_model=UserListResponse)
def list_users(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    _: CurrentUser = Depends(get_current_admin),
):
    """
    Admin: list all registered customers. Paginated, newest first.

    Note: Role promotion (user → admin) is intentionally not exposed
    via this API to prevent privilege escalation. Use the SQL function:
      SELECT promote_to_admin('<user-uuid>');
    """
    repo = UserRepository()
    users, total = repo.get_all(page=page, page_size=page_size)
    return UserListResponse(
        items=[UserResponse(**u) for u in users],
        total=total,
    )


@router.get("/{user_id}", response_model=UserResponse)
def get_user(
    user_id: str,
    _: CurrentUser = Depends(get_current_admin),
):
    """Admin: fetch a single user profile by ID."""
    repo = UserRepository()
    user = repo.get_by_id(user_id)
    return UserResponse(**user)
