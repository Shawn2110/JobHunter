from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    """JobHunt backend configuration.

    Loaded from `.env` at the repo root. Every external-service key is
    optional. The backend detects which providers are configured at
    startup and only enables those — see `configured_aggregators`,
    `configured_search_provider`, and `has_ai`.
    """

    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env",),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ── Server ──────────────────────────────────────────────────────────────
    backend_host: str = "127.0.0.1"
    backend_port: int = 8000
    bind_public: bool = False
    frontend_origin: str = "http://localhost:3000"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # ── Database ────────────────────────────────────────────────────────────
    database_url: str = "sqlite+aiosqlite:///./data/jobhunt.db"

    # ── AI provider (Anthropic Claude) ──────────────────────────────────────
    anthropic_api_key: str | None = None
    anthropic_model_default: str = "claude-sonnet-4-6"
    anthropic_model_high_stakes: str = "claude-opus-4-7"

    # ── Job aggregators (Discovery Mode 1) ──────────────────────────────────
    jsearch_api_key: str | None = None
    adzuna_app_id: str | None = None
    adzuna_app_key: str | None = None
    jooble_api_key: str | None = None
    theirstack_api_key: str | None = None

    # ── Search APIs (LinkedIn URL discovery, signal aggregation) ────────────
    brave_search_api_key: str | None = None
    serper_api_key: str | None = None

    # ── Careers-page crawler ────────────────────────────────────────────────
    firecrawl_api_key: str | None = None

    # ── Public profile signals ──────────────────────────────────────────────
    github_token: str | None = None

    # ── Derived properties ──────────────────────────────────────────────────

    @property
    def has_ai(self) -> bool:
        return bool(self.anthropic_api_key)

    @property
    def configured_aggregators(self) -> list[str]:
        out: list[str] = []
        if self.jsearch_api_key:
            out.append("jsearch")
        if self.adzuna_app_id and self.adzuna_app_key:
            out.append("adzuna")
        if self.jooble_api_key:
            out.append("jooble")
        if self.theirstack_api_key:
            out.append("theirstack")
        return out

    @property
    def configured_search_provider(self) -> str | None:
        if self.brave_search_api_key:
            return "brave"
        if self.serper_api_key:
            return "serper"
        return None

    @property
    def configured_crawler(self) -> str:
        return "firecrawl" if self.firecrawl_api_key else "playwright"

    def host_for_uvicorn(self) -> str:
        # When bound publicly (VPS deploy behind Cloudflare Tunnel), listen
        # on all interfaces. Otherwise, localhost only.
        return "0.0.0.0" if self.bind_public else self.backend_host  # noqa: S104


settings = Settings()
