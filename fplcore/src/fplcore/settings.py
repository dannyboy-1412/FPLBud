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

    chat_enabled: bool = False
    chat_llm_model: str = ""
    chat_llm_fallback_model: str = ""
    chat_llm_base_url: str = ""
    chat_llm_api_key: str = ""
    chat_price_input_per_mtok: float | None = None
    chat_price_output_per_mtok: float | None = None
    chat_price_cached_per_mtok: float | None = None
    chat_max_tool_rounds: int = 6
    chat_max_tool_calls: int = 10
    chat_turn_timeout_seconds: float = 60
    chat_max_output_tokens: int = 900
    chat_turn_input_token_cap: int = 40_000
    chat_max_input_chars: int = 1500
    chat_history_token_budget: int = 6000
    chat_tool_result_token_cap: int = 1500
    chat_max_concurrent_turns: int = 4
    chat_user_turns_per_day: int = 20
    chat_user_turns_per_day_noteam: int = 10
    chat_user_turns_per_minute: int = 4
    chat_user_optimiser_per_hour: int = 20
    chat_global_daily_cost_usd: float = 2.0
    chat_guest_enabled: bool = False
    chat_retention_days: int = 90
    chat_trace_retention_days: int = 14
    chat_store_tool_results: bool = True
    chat_allowed_user_ids: str = ""
    chat_admin_user_ids: str = ""

    cors_allowed_origins: str = "http://localhost:3000,https://fplbud.vercel.app"

    @field_validator(
        "chat_price_input_per_mtok",
        "chat_price_output_per_mtok",
        "chat_price_cached_per_mtok",
        mode="before",
    )
    @classmethod
    def blank_price_is_unset(cls, value: object) -> object:
        if value is None or value == "":
            return None
        return value

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

    @property
    def resolved_chat_model(self) -> str:
        return self.chat_llm_model or self.llm_model

    @property
    def resolved_chat_api_key(self) -> str:
        return self.chat_llm_api_key or self.llm_api_key

    @property
    def resolved_chat_base_url(self) -> str:
        return (self.chat_llm_base_url or self.llm_base_url).rstrip("/")

    @property
    def chat_allowed_ids(self) -> set[str]:
        return {item.strip() for item in self.chat_allowed_user_ids.split(",") if item.strip()}

    @property
    def chat_admin_ids(self) -> set[str]:
        return {item.strip() for item in self.chat_admin_user_ids.split(",") if item.strip()}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
