from __future__ import annotations

from datetime import datetime

import httpx

from app.config import settings
from app.discovery.adapters.base import DiscoveryAdapter
from app.discovery.types import DiscoveredJob, SearchInput


class AdzunaAdapter(DiscoveryAdapter):
    """Adzuna — global aggregator with strong India + EU coverage.

    Free tier with attribution. Country code defaults to "in" (India)
    when locations include any Indian city; falls back to "us"
    otherwise. Override via per-search heuristic if needed.
    """

    name = "adzuna"
    source_kind = "aggregator"

    BASE = "https://api.adzuna.com/v1/api/jobs"

    _IN_CITIES = {"bengaluru", "bangalore", "mumbai", "hyderabad", "pune", "delhi", "ncr", "chennai", "gurugram", "noida"}

    def is_configured(self) -> bool:
        return bool(settings.adzuna_app_id and settings.adzuna_app_key)

    def _country(self, query: SearchInput) -> str:
        for loc in query.locations:
            if any(c in loc.lower() for c in self._IN_CITIES):
                return "in"
        return "us"

    async def _fetch(self, query: SearchInput) -> list[DiscoveredJob]:
        country = self._country(query)
        params: dict[str, str | int] = {
            "app_id": settings.adzuna_app_id or "",
            "app_key": settings.adzuna_app_key or "",
            "results_per_page": query.per_page,
            "what": query.role,
            "content-type": "application/json",
        }
        if query.locations:
            params["where"] = query.locations[0]
        if query.salary_floor:
            params["salary_min"] = query.salary_floor

        url = f"{self.BASE}/{country}/search/{query.page}"
        async with httpx.AsyncClient(timeout=15.0) as client:
            res = await client.get(url, params=params)
            res.raise_for_status()
        return [_parse(row) for row in res.json().get("results", [])]


def _parse(row: dict) -> DiscoveredJob:
    posted = None
    if row.get("created"):
        try:
            posted = datetime.fromisoformat(row["created"].replace("Z", "+00:00"))
        except (ValueError, TypeError):
            posted = None

    salary_text = None
    if row.get("salary_min") or row.get("salary_max"):
        salary_text = f"{row.get('salary_min', '')}-{row.get('salary_max', '')} {row.get('salary_currency', '')}".strip()

    return DiscoveredJob(
        title=row.get("title", "Untitled").strip(),
        company=(row.get("company") or {}).get("display_name", "Unknown"),
        location=(row.get("location") or {}).get("display_name"),
        work_mode=None,
        salary_text=salary_text,
        description_md=row.get("description"),
        posted_at=posted,
        apply_url=row.get("redirect_url"),
        source_provider="adzuna",
    )
