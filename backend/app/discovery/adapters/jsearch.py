from __future__ import annotations

from datetime import datetime, timezone

import httpx

from app.config import settings
from app.discovery.adapters.base import DiscoveryAdapter
from app.discovery.types import DiscoveredJob, SearchInput


class JSearchAdapter(DiscoveryAdapter):
    """JSearch via RapidAPI — global aggregator."""

    name = "jsearch"
    source_kind = "aggregator"

    BASE = "https://jsearch.p.rapidapi.com/search"

    def is_configured(self) -> bool:
        return bool(settings.jsearch_api_key)

    async def _fetch(self, query: SearchInput) -> list[DiscoveredJob]:
        # JSearch combines role + location into a single `query` string.
        location_part = (
            " in " + ", ".join(query.locations) if query.locations else ""
        )
        params: dict[str, str | int] = {
            "query": f"{query.role}{location_part}",
            "page": query.page,
            "num_pages": 1,
        }
        if query.work_mode and query.work_mode != "any":
            params["work_from_home"] = "true" if query.work_mode == "remote" else "false"

        headers = {
            "X-RapidAPI-Key": settings.jsearch_api_key or "",
            "X-RapidAPI-Host": "jsearch.p.rapidapi.com",
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            res = await client.get(self.BASE, params=params, headers=headers)
            res.raise_for_status()

        body = res.json()
        return [_parse(row) for row in body.get("data", [])]


def _parse(row: dict) -> DiscoveredJob:
    posted = None
    posted_ts = row.get("job_posted_at_timestamp")
    if posted_ts:
        try:
            posted = datetime.fromtimestamp(int(posted_ts), tz=timezone.utc)
        except (ValueError, OSError):
            posted = None

    location_parts = [
        p for p in (row.get("job_city"), row.get("job_country")) if p
    ]
    location = ", ".join(location_parts) if location_parts else None

    work_mode = None
    if row.get("job_is_remote"):
        work_mode = "remote"

    salary_text = None
    if row.get("job_min_salary") or row.get("job_max_salary"):
        ccy = row.get("job_salary_currency", "")
        period = row.get("job_salary_period", "")
        salary_text = (
            f"{row.get('job_min_salary', '')}-{row.get('job_max_salary', '')} "
            f"{ccy} {period}".strip()
        )

    return DiscoveredJob(
        title=row.get("job_title", "Untitled"),
        company=row.get("employer_name", "Unknown"),
        location=location,
        work_mode=work_mode,
        salary_text=salary_text,
        description_md=row.get("job_description"),
        posted_at=posted,
        apply_url=row.get("job_apply_link") or row.get("job_google_link"),
        source_provider="jsearch",
    )
