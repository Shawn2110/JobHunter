from __future__ import annotations

from datetime import datetime

import httpx

from app.config import settings
from app.discovery.adapters.base import DiscoveryAdapter
from app.discovery.types import DiscoveredJob, SearchInput


class JoobleAdapter(DiscoveryAdapter):
    """Jooble — global aggregator with generous free tier."""

    name = "jooble"
    source_kind = "aggregator"

    def is_configured(self) -> bool:
        return bool(settings.jooble_api_key)

    async def _fetch(self, query: SearchInput) -> list[DiscoveredJob]:
        url = f"https://jooble.org/api/{settings.jooble_api_key}"
        body: dict[str, str | int] = {
            "keywords": query.role,
            "page": str(query.page),
        }
        if query.locations:
            body["location"] = ", ".join(query.locations)
        if query.salary_floor:
            body["salary"] = str(query.salary_floor)

        async with httpx.AsyncClient(timeout=15.0) as client:
            res = await client.post(url, json=body)
            res.raise_for_status()
        return [_parse(row) for row in res.json().get("jobs", [])]


def _parse(row: dict) -> DiscoveredJob:
    posted = None
    if row.get("updated"):
        try:
            posted = datetime.fromisoformat(row["updated"].replace("Z", "+00:00"))
        except (ValueError, TypeError):
            posted = None

    return DiscoveredJob(
        title=row.get("title", "Untitled"),
        company=row.get("company", "Unknown"),
        location=row.get("location"),
        work_mode=None,
        salary_text=row.get("salary"),
        description_md=row.get("snippet"),
        posted_at=posted,
        apply_url=row.get("link"),
        source_provider="jooble",
    )
