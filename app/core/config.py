"""
Application configuration using pydantic-settings.
All values come from environment variables or .env file.
Cached with @lru_cache so Settings() is only created once per process.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",           # silently ignore unknown env vars
    )

    # Application
    app_name: str    = "Vendora API"
    app_version: str = "1.0.0"
    app_env: str     = "development"
    debug: bool      = False

    # Supabase — all required, app refuses to start without them
    supabase_url:              str
    supabase_anon_key:         str
    supabase_service_role_key: str
    supabase_jwt_secret:       str

    # Paystack — empty defaults so app starts without payment config in dev
    paystack_secret_key:    str = ""
    paystack_public_key:    str = ""
    paystack_webhook_secret: str = ""

    # CORS — comma-separated list of allowed frontend origins
    allowed_origins: str = "http://localhost:5173"

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",")]

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    """Return the singleton Settings instance. Cached after first call."""
    return Settings()