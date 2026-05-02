from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx
import structlog

from app.discovery.types import DiscoveredJob

log = structlog.get_logger("app.discovery.lever")

API_TEMPLATE = "https://api.lever.co/v0/postings/{slug}?mode=json"


async def fetch_for_slug(slug: str, client: httpx.AsyncClient | None = None) -> list[DiscoveredJob]:
    """Pull every posting from one Lever postings board.

    Public, keyless, documented at api.lever.co. Returns a top-level
    JSON array, one posting per element.
    """
    own_client = client is None
    if own_client:
        client = httpx.AsyncClient(
            timeout=20.0,
            headers={"User-Agent": "JobHunt/0.1 (self-hosted, local-only)"},
        )
    try:
        res = await client.get(API_TEMPLATE.format(slug=slug))
        if res.status_code == 404:
            log.info("lever.unknown_slug", slug=slug)
            return []
        res.raise_for_status()
        body = res.json()
    finally:
        if own_client:
            await client.aclose()  # type: ignore[union-attr]

    if not isinstance(body, list):
        log.warning("lever.unexpected_shape", slug=slug, type=type(body).__name__)
        return []

    company = slug.replace("-", " ").replace("_", " ").title()
    out: list[DiscoveredJob] = []
    for j in body:
        out.append(_parse(j, company))
    log.info("lever.fetched", slug=slug, count=len(out))
    return out


def _parse(j: dict[str, Any], company: str) -> DiscoveredJob:
    cats = j.get("categories") or {}
    posted_ms = j.get("createdAt")
    posted: datetime | None = None
    if isinstance(posted_ms, int):
        try:
            posted = datetime.fromtimestamp(posted_ms / 1000, tz=timezone.utc)
        except (ValueError, OSError):
            posted = None

    work_mode_raw = (cats.get("commitment") or "").lower()
    if "remote" in (cats.get("location") or "").lower() or work_mode_raw == "remote":
        work_mode = "remote"
    elif work_mode_raw in {"hybrid", "onsite", "on-site"}:
        work_mode = work_mode_raw
    else:
        work_mode = None

    description = j.get("descriptionPlain") or _flatten_description_html(j.get("description", ""))
    return DiscoveredJob(
        title=j.get("text", "Untitled"),
        company=company,
        location=cats.get("location"),
        work_mode=work_mode,
        salary_text=None,
        description_md=description[:8000] if description else None,
        posted_at=posted,
        apply_url=j.get("hostedUrl") or j.get("applyUrl"),
        source_provider="lever",
    )


def _flatten_description_html(html: str) -> str:
    import re
    text = re.sub(r"<[^>]+>", " ", html or "")
    return re.sub(r"\s+", " ", text).strip()
