"""Customer — Profile Endpoints."""
import uuid
from fastapi import APIRouter, Depends, File, UploadFile
from app.core.exceptions import ValidationError
from app.core.supabase import get_supabase_admin_client
from app.dependencies.auth import get_current_user
from app.schemas.user import CurrentUser, ProfileResponse, ProfileUpdate
from app.services.profile_service import ProfileService

router = APIRouter(prefix="/profile", tags=["Customer — Profile"])

AVATAR_BUCKET   = "avatars"
AVATAR_MAX_SIZE = 2 * 1024 * 1024
AVATAR_ALLOWED  = {"image/jpeg", "image/png", "image/webp"}


@router.get("", response_model=ProfileResponse)
def get_profile(
    current_user: CurrentUser = Depends(get_current_user),
    service: ProfileService = Depends(ProfileService),
):
    """Get the authenticated user's full profile."""
    return service.get_profile(current_user.id)


@router.patch("", response_model=ProfileResponse)
def update_profile(
    payload: ProfileUpdate,
    current_user: CurrentUser = Depends(get_current_user),
    service: ProfileService = Depends(ProfileService),
):
    """Update profile. Only send the fields you want to change."""
    return service.update_profile(current_user.id, payload)


@router.post("/avatar", response_model=ProfileResponse)
async def upload_avatar(
    file: UploadFile = File(...),
    current_user: CurrentUser = Depends(get_current_user),
    service: ProfileService = Depends(ProfileService),
):
    """Upload a profile picture (JPEG/PNG/WebP, max 2 MB)."""
    if file.content_type not in AVATAR_ALLOWED:
        raise ValidationError(f"File type '{file.content_type}' is not allowed.")
    contents = await file.read()
    if len(contents) > AVATAR_MAX_SIZE:
        raise ValidationError("File exceeds the 2 MB size limit.")

    ext  = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else "jpg"
    path = f"{current_user.id}/{uuid.uuid4()}.{ext}"

    db = get_supabase_admin_client()
    db.storage.from_(AVATAR_BUCKET).upload(
        path=path, file=contents,
        file_options={"content-type": file.content_type, "upsert": "true"},
    )
    avatar_url = db.storage.from_(AVATAR_BUCKET).get_public_url(path)
    return service.set_avatar_url(current_user.id, avatar_url)