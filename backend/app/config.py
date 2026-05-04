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
    # Default resolves to <repo_root>/data/jobhunt.db so the same URL works
    # whether the process runs from the repo root, from backend/, or inside
    # the Docker container. Override with DATABASE_URL in .env if you want
    # the file elsewhere.
    database_url: str = (
        f"sqlite+aiosqlite:///{(REPO_ROOT / 'data' / 'jobhunt.db').as_posix()}"
    )

    # ── AI provider (Anthropic Claude) ──────────────────────────────────────
    anthropic_api_key: str | None = None
    anthropic_model_default: str = "claude-sonnet-4-6"
    anthropic_model_high_stakes: str = "claude-opus-4-7"

    # ── Search APIs (LinkedIn URL discovery, signal aggregation) ────────────
    brave_search_api_key: str | None = None
    serper_api_key: str | None = None

    # ── Careers-page crawler ────────────────────────────────────────────────
    firecrawl_api_key: str | None = None

    # ── Apify (optional, for SPA portals Naukri/Foundit/Wellfound) ──────────
    # Set APIFY_API_TOKEN + per-portal Actor IDs to enable. Leave any
    # actor blank to disable that portal. LinkedIn is intentionally
    # NOT supported here; see ADR 0006.
    apify_api_token: str | None = None
    apify_naukri_actor: str | None = None  # e.g. "epctex/naukri-scraper"
    apify_foundit_actor: str | None = None
    apify_wellfound_actor: str | None = None

    # ── Public profile signals ──────────────────────────────────────────────
    github_token: str | None = None

    # ── Derived properties ──────────────────────────────────────────────────

    @property
    def has_ai(self) -> bool:
        return bool(self.anthropic_api_key)

    def get_apify_actor(self, portal: str) -> str | None:
        """Look up the configured Apify Actor ID for a portal name.

        Returns None if Apify isn't configured or this portal isn't
        wired up. Caller should treat None as 'skip Apify path'.
        """
        if not self.apify_api_token:
            return None
        if portal == "naukri":
            return self.apify_naukri_actor
        if portal == "foundit":
            return self.apify_foundit_actor
        if portal == "wellfound":
            return self.apify_wellfound_actor
        return None

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
