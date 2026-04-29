"""Admin — Users (read-only + profile endpoint)."""
from fastapi import APIRouter, Depends, Query
from app.dependencies.auth import get_current_admin
from app.repositories.user_repository import UserRepository
from app.schemas.user import CurrentUser, ProfileResponse, UserListResponse, UserResponse
from app.services.profile_service import ProfileService

router = APIRouter(prefix="/admin/users", tags=["Admin — Users"])


@router.get("", response_model=UserListResponse)
def list_users(page: int = Query(default=1, ge=1), page_size: int = Query(default=20, ge=1, le=100), _: CurrentUser = Depends(get_current_admin)):
    repo = UserRepository()
    users, total = repo.get_all(page=page, page_size=page_size)
    return UserListResponse(items=[UserResponse(**u) for u in users], total=total)


@router.get("/{user_id}", response_model=UserResponse)
def get_user(user_id: str, _: CurrentUser = Depends(get_current_admin)):
    return UserResponse(**UserRepository().get_by_id(user_id))


@router.get("/{user_id}/profile", response_model=ProfileResponse)
def get_user_profile(user_id: str, _: CurrentUser = Depends(get_current_admin), service: ProfileService = Depends(ProfileService)):
    return service.get_profile(user_id)