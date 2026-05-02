from __future__ import annotations

import re
from datetime import datetime
from typing import Any

import httpx
import structlog

from app.discovery.types import DiscoveredJob

log = structlog.get_logger("app.discovery.greenhouse")

API_TEMPLATE = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true"


async def fetch_for_slug(slug: str, client: httpx.AsyncClient | None = None) -> list[DiscoveredJob]:
    """Pull every job from one Greenhouse board.

    Endpoint is keyless and ToS-clean — it's the same JSON the public
    `boards.greenhouse.io/{slug}` page hydrates from.
    """
    own_client = client is None
    if own_client:
        client = httpx.AsyncClient(
            timeout=20.0,
            headers={"User-Agent": "JobHunt/0.1 (self-hosted, local-only)"},
        )
    try:
        url = API_TEMPLATE.format(slug=slug)
        res = await client.get(url)
        if res.status_code == 404:
            log.info("greenhouse.unknown_slug", slug=slug)
            return []
        res.raise_for_status()
        body = res.json()
    finally:
        if own_client:
            await client.aclose()  # type: ignore[union-attr]

    jobs = body.get("jobs") or []
    out: list[DiscoveredJob] = []
    for j in jobs:
        out.append(_parse(j, slug))
    log.info("greenhouse.fetched", slug=slug, count=len(out))
    return out


def _parse(j: dict[str, Any], slug: str) -> DiscoveredJob:
    company_name = _company_from_slug(slug)
    location = (j.get("location") or {}).get("name")
    posted = _parse_iso_date(j.get("updated_at"))
    description = _strip_html(j.get("content", ""))
    return DiscoveredJob(
        title=j.get("title", "Untitled"),
        company=company_name,
        location=location,
        work_mode=None,
        salary_text=None,
        description_md=description[:8000] if description else None,
        posted_at=posted,
        apply_url=j.get("absolute_url"),
        source_provider="greenhouse",
    )


def _company_from_slug(slug: str) -> str:
    """Best-effort title-case rendering of the slug ('postman' → 'Postman').

    Some slugs encode multi-word names ('postmanlabs', 'thinkific'); we
    leave these as-is since we don't have ground truth.
    """
    return slug.replace("-", " ").replace("_", " ").title()


_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def _strip_html(html: str) -> str:
    text = _TAG_RE.sub(" ", html or "")
    return _WS_RE.sub(" ", text).strip()


def _parse_iso_date(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
