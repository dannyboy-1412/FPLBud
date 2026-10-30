from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / ".env").exists() or (
            (parent / "pyproject.toml").exists() and (parent / "fplcore").is_dir() and (parent / "api").is_dir()
        ):
            return parent
    return Path.cwd()


_ROOT = _repo_root()


def split_origins(value: str) -> list[str]:
    return [item.strip().rstrip("/") for item in value.split(",") if item.strip()]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: str = "development"
    next_public_site_url: str = "http://localhost:3000"
    next_public_api_url: str = "http://localhost:8000"

    next_public_supabase_url: str = ""
    next_public_supabase_anon_key: str = ""
    supabase_service_role_key: str = ""
    supabase_jwt_secret: str = ""
    database_url: str = ""
    db_pool_min_size: int = 1
    db_pool_max_size: int = 8

    fpl_api_base_url: str = "https://fantasy.premierleague.com/api"
    fpl_request_timeout_seconds: float = 15
    fpl_max_requests_per_second: float = 3

    internal_api_secret: str = ""
    agent_poll_interval_seconds: float = 5
    agent_job_timeout_seconds: float = 300
    agent_max_attempts: int = 3
    agent_tracking_window_days: int = 30

    llm_enabled: bool = False
    llm_provider: str = "openrouter"
    llm_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("LLM_API_KEY", "OPENROUTER_API_KEY"),
    )
    llm_model: str = ""
    llm_base_url: str = "https://openrouter.ai/api/v1"
    llm_timeout_seconds: float = 10
    llm_lineup_timeout_seconds: float = 45
    llm_lineup_max_searches: int = 4
    llm_daily_call_cap: int = 200

    sentry_dsn: str = ""

    guest_rate_limit_per_minute: int = 10
    user_rate_limit_per_minute: int = 30
    agent_rerun_limit_per_hour: int = 6

    cors_allowed_origins: str = "http://localhost:3000,https://fplbud.vercel.app"

    @field_validator("fpl_api_base_url")
    @classmethod
    def strip_trailing_slash(cls, value: str) -> str:
        return value.rstrip("/")

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    @property
    def supabase_url(self) -> str:
        return self.next_public_supabase_url.rstrip("/").removesuffix("/rest/v1")

    @property
    def cors_origins(self) -> list[str]:
        return split_origins(self.cors_allowed_origins)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
