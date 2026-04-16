"""
Application Configuration.

All settings are loaded from environment variables (or a .env file).
Uses pydantic-settings for type-safe, validated configuration.

The @lru_cache on get_settings() ensures the Settings object is only
created once per process — safe and efficient for use in FastAPI
Depends() or direct imports throughout the codebase.

Required variables (no defaults — app will refuse to start if missing):
  SUPABASE_URL
  SUPABASE_ANON_KEY
  SUPABASE_SERVICE_ROLE_KEY
  SUPABASE_JWT_SECRET

All other variables have safe defaults for local development.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        # Extra env vars present in the file are silently ignored
        extra="ignore",
    )

    # ─── Application ──────────────────────────────────────────────────────────
    app_name: str = "E-Commerce API"
    app_version: str = "1.0.0"
    # "development" | "staging" | "production"
    app_env: str = "development"
    debug: bool = False

    # ─── Supabase ─────────────────────────────────────────────────────────────
    # All four are required — the app cannot start without them.
    supabase_url: str
    supabase_anon_key: str
    supabase_service_role_key: str
    # Found in: Supabase Dashboard → Settings → API → JWT Secret
    supabase_jwt_secret: str

    # ─── Paystack (Payment Gateway) ───────────────────────────────────────────
    # Empty defaults so the app starts in dev even without payment config.
    # Payment endpoints will fail at runtime if these are not set.
    paystack_secret_key: str = ""
    paystack_public_key: str = ""
    paystack_webhook_secret: str = ""

    # ─── CORS ─────────────────────────────────────────────────────────────────
    # Comma-separated list of allowed origins.
    # Example: "http://localhost:3000,https://myapp.com"
    allowed_origins: str = "http://localhost:3000"

    # ─── Computed Properties ──────────────────────────────────────────────────

    @property
    def cors_origins(self) -> list[str]:
        """Parse comma-separated ALLOWED_ORIGINS into a list."""
        return [origin.strip() for origin in self.allowed_origins.split(",")]

    @property
    def is_production(self) -> bool:
        """True when APP_ENV=production. Used to toggle docs, log format, etc."""
        return self.app_env.lower() == "production"

    @property
    def is_development(self) -> bool:
        return self.app_env.lower() == "development"


@lru_cache
def get_settings() -> Settings:
    """
    Return the cached application settings singleton.

    Using @lru_cache means Settings() is only instantiated once per
    process, no matter how many times get_settings() is called.

    In tests, override with:
        app.dependency_overrides[get_settings] = lambda: Settings(...)
    """
    return Settings()

