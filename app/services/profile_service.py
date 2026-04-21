"""Profile Service."""
from app.repositories.profile_repository import ProfileRepository
from app.schemas.user import ProfileResponse, ProfileUpdate


class ProfileService:
    def __init__(self):
        self.repo = ProfileRepository()

    def get_profile(self, user_id: str) -> ProfileResponse:
        return ProfileResponse(**self.repo.get_by_user_id(user_id))

    def update_profile(self, user_id: str, data: ProfileUpdate) -> ProfileResponse:
        payload = data.model_dump(exclude_unset=True)
        if payload:
            self.repo.upsert(user_id, payload)
        return self.get_profile(user_id)

    def set_avatar_url(self, user_id: str, avatar_url: str) -> ProfileResponse:
        self.repo.upsert(user_id, {"avatar_url": avatar_url})
        return self.get_profile(user_id)