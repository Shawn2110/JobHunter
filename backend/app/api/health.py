from __future__ import annotations

from fastapi import APIRouter

from app import __version__
from app.config import settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe used by docker-compose and the frontend."""
    return {"status": "ok"}


@router.get("/providers")
async def providers() -> dict[str, object]:
    """Reports which optional providers are configured.

    Frontend can use this to surface "not configured" hints in the UI
    without exposing the actual API keys.
    """
    return {
        "version": __version__,
        "ai_configured": settings.has_ai,
        "search_provider": settings.configured_search_provider,
        "crawler": settings.configured_crawler,
        "github_token_configured": bool(settings.github_token),
    }
