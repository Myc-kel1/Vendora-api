"""
Customer — Profile endpoints.

GET  /profile         — view own profile (merges profiles + users tables)
PATCH /profile        — update own profile (partial update, send only changed fields)
POST /profile/avatar  — upload profile picture to Supabase Storage

Avatar upload uses magic byte validation to prevent content-type spoofing.
The file path is scoped to the user's UUID, matching the RLS policy:
  auth.uid()::text = (storage.foldername(name))[1]
"""
import uuid
from fastapi import APIRouter, Depends, File, UploadFile
from app.core.exceptions import ValidationError
from app.core.supabase import get_supabase_admin_client
from app.dependencies.auth import get_current_user
from app.schemas.user import CurrentUser, ProfileResponse, ProfileUpdate
from app.services.profile_service import ProfileService

router = APIRouter(prefix="/profile", tags=["Customer — Profile"])

AVATAR_BUCKET   = "avatars"
AVATAR_MAX_SIZE = 2 * 1024 * 1024   # 2 MB

# Magic bytes for allowed avatar image types
AVATAR_MAGIC = {
    b"\xff\xd8\xff": "image/jpeg",
    b"\x89PNG\r\n":  "image/png",
    b"RIFF":         "image/webp",
}


def _validate_avatar(contents: bytes, declared_type: str) -> str:
    """Validate avatar by magic bytes. Returns detected MIME type."""
    for magic, mime in AVATAR_MAGIC.items():
        if contents[:len(magic)] == magic:
            if magic == b"RIFF" and contents[8:12] != b"WEBP":
                continue
            return mime
    raise ValidationError(
        f"File is not a valid image. Supported: JPEG, PNG, WebP. "
        f"(Declared: {declared_type})"
    )


@router.get("", response_model=ProfileResponse)
def get_profile(
    current_user: CurrentUser = Depends(get_current_user),
    service: ProfileService = Depends(ProfileService),
):
    """
    Get the authenticated user's full profile.
    Merges public.profiles (name, address…) with public.users (email, role).
    Auto-creates an empty profile row if one doesn't exist yet.
    """
    return service.get_profile(current_user.id)


@router.patch("", response_model=ProfileResponse)
def update_profile(
    payload: ProfileUpdate,
    current_user: CurrentUser = Depends(get_current_user),
    service: ProfileService = Depends(ProfileService),
):
    """
    Partially update the authenticated user's profile.
    Only the fields you send will be changed.
    Example: { "first_name": "Ada", "city": "Lagos" }
    """
    return service.update_profile(current_user.id, payload)


@router.post("/avatar", response_model=ProfileResponse)
async def upload_avatar(
    file: UploadFile = File(...),
    current_user: CurrentUser = Depends(get_current_user),
    service: ProfileService = Depends(ProfileService),
):
    """
    Upload a profile picture.

    Process:
      1. Read file bytes
      2. Validate size (≤ 2 MB)
      3. Validate by magic bytes (prevents content-type spoofing)
      4. Store at: avatars/<user_id>/<uuid>.<ext>
         Path is scoped to user_id — matches RLS policy
      5. Save public URL to profiles.avatar_url

    Supported: JPEG, PNG, WebP
    Max size: 2 MB
    """
    contents = await file.read()

    if len(contents) > AVATAR_MAX_SIZE:
        raise ValidationError(
            f"File size {len(contents) / 1024 / 1024:.1f} MB exceeds the 2 MB limit"
        )

    detected_mime = _validate_avatar(contents, file.content_type or "unknown")

    ext_map = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}
    ext  = ext_map.get(detected_mime, "jpg")

    # Path MUST start with user_id to satisfy RLS policy:
    # auth.uid()::text = (storage.foldername(name))[1]
    path = f"{current_user.id}/{uuid.uuid4()}.{ext}"

    db = get_supabase_admin_client()
    db.storage.from_(AVATAR_BUCKET).upload(
        path=path,
        file=contents,
        file_options={"content-type": detected_mime, "upsert": "true"},
    )

    avatar_url = db.storage.from_(AVATAR_BUCKET).get_public_url(path)
    return service.set_avatar_url(current_user.id, avatar_url)