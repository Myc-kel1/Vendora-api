from functools import lru_cache
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ─── App ─────────────────────────────
    app_name: str = "E-Commerce API"
    app_version: str = "1.0.0"
    app_env: str = "development"
    debug: bool = False

    # ─── Supabase ────────────────────────
    supabase_url: str
    supabase_anon_key: str
    supabase_service_role_key: str
    supabase_jwt_secret: str

    # ─── Paystack ────────────────────────
    paystack_secret_key: str = ""
    paystack_public_key: str = ""
    paystack_webhook_secret: str = ""

    # ─── CORS (IMPORTANT FIX) ────────────
    allowed_origins: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:5174",
        "https://vendora-customer-ui.onrender.com",
        "https://vendora-admin-ui.onrender.com",
    ]

    # ─── Helpers ─────────────────────────
    @property
    def cors_origins(self) -> List[str]:
        return self.allowed_origins

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    @property
    def is_development(self) -> bool:
        return self.app_env.lower() == "development"


@lru_cache
def get_settings() -> Settings:
    return Settings()