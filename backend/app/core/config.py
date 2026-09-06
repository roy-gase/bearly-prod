"""Application settings, loaded from the environment.

Every secret arrives via environment variable so nothing sensitive is committed
or shipped to the browser.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_prefix="BEARLY_", extra="ignore", case_sensitive=False
    )

    app_name: str = "Bearly"
    environment: Literal["development", "staging", "production"] = "development"
    api_prefix: str = "/api/v1"

    secret_key: str = "dev-insecure-change-me"
    access_token_minutes: int = 60
    refresh_token_days: int = 14
    password_reset_minutes: int = 30

    database_url: str = "sqlite:///./bearly.db"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    # Host header allowlist. "*" is refused in production.
    trusted_hosts: str = "*"
    db_pool_size: int = 5
    db_max_overflow: int = 10
    log_json: bool = False

    # --- Brute-force protection ------------------------------------------
    # Tracked in the database, so the limit holds across every worker rather
    # than per-process the way an in-memory counter would.
    max_failed_logins: int = 8
    lockout_minutes: int = 15

    # --- Outbound email (password reset) ---------------------------------
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "Bearly <no-reply@bearly.app>"
    smtp_starttls: bool = True
    app_base_url: str = "http://localhost:5173"
    # Escape hatch for a first deploy before SMTP exists. Password reset is
    # non-functional while this is on, so it logs loudly on every start.
    allow_no_email: bool = False

    # --- AI ---------------------------------------------------------------
    ai_provider: Literal["stub", "anthropic", "tenki"] = "stub"
    ai_routine_model: str = "claude-haiku-4-5"
    ai_planner_model: str = "claude-opus-5"
    # Chat is many short turns, so it defaults to the cheap model.
    ai_chat_model: str = "claude-haiku-4-5"
    ai_max_output_tokens: int = 1500
    ai_cache_hours: int = 24
    ai_timeout_seconds: float = 90.0

    tenki_sandbox_timeout: int = 120

    # Read without the BEARLY_ prefix so they match each vendor's convention.
    anthropic_api_key: str = Field(default="", validation_alias="ANTHROPIC_API_KEY")
    tenki_api_key: str = Field(default="", validation_alias="TENKI_API_KEY")

    @field_validator("database_url")
    @classmethod
    def _normalise_database_url(cls, v: str) -> str:
        """Accept the connection strings hosting providers actually hand out.

        Render, Railway, Heroku and Fly all supply `postgres://...`, which
        SQLAlchemy 2 refuses, and `postgresql://` selects psycopg2, which is not
        installed. Both are rewritten to the psycopg 3 driver so the value can be
        pasted in unmodified.
        """
        if v.startswith("postgres://"):
            return "postgresql+psycopg://" + v[len("postgres://"):]
        if v.startswith("postgresql://"):
            return "postgresql+psycopg://" + v[len("postgresql://"):]
        return v

    @field_validator("secret_key")
    @classmethod
    def _require_strong_secret_in_prod(cls, v: str, info) -> str:
        """Fail fast at import rather than serve signable tokens with a known key."""
        if info.data.get("environment") != "production":
            return v
        if v == "dev-insecure-change-me":
            raise ValueError("BEARLY_SECRET_KEY must be set in production")
        if len(v) < 32:
            raise ValueError("BEARLY_SECRET_KEY must be at least 32 characters in production")
        return v

    @field_validator("trusted_hosts")
    @classmethod
    def _require_host_allowlist_in_prod(cls, v: str, info) -> str:
        if info.data.get("environment") == "production" and v.strip() == "*":
            raise ValueError(
                "BEARLY_TRUSTED_HOSTS must list your real hostnames in production"
            )
        return v

    @field_validator("cors_origins")
    @classmethod
    def _reject_wildcard_cors_in_prod(cls, v: str, info) -> str:
        if info.data.get("environment") == "production" and "*" in v:
            raise ValueError("BEARLY_CORS_ORIGINS cannot contain a wildcard in production")
        return v

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def cookie_secure(self) -> bool:
        return self.environment == "production"

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def trusted_host_list(self) -> list[str]:
        return [h.strip() for h in self.trusted_hosts.split(",") if h.strip()]

    @property
    def email_configured(self) -> bool:
        return bool(self.smtp_host)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
