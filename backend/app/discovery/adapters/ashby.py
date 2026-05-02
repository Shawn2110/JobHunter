from __future__ import annotations

import re
from datetime import datetime
from typing import Any

import httpx
import structlog

from app.discovery.types import DiscoveredJob

log = structlog.get_logger("app.discovery.ashby")

API_TEMPLATE = "https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true"


async def fetch_for_slug(slug: str, client: httpx.AsyncClient | None = None) -> list[DiscoveredJob]:
    """Pull every posting from one Ashby job board.

    Endpoint is public; the slug is the company's Ashby tenant
    (e.g., 'anthropic' for jobs.ashbyhq.com/anthropic).
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
            log.info("ashby.unknown_slug", slug=slug)
            return []
        res.raise_for_status()
        body = res.json()
    finally:
        if own_client:
            await client.aclose()  # type: ignore[union-attr]

    company = body.get("title") or slug.replace("-", " ").replace("_", " ").title()
    jobs = body.get("jobs") or []
    out: list[DiscoveredJob] = []
    for j in jobs:
        if j.get("isListed") is False:
            continue
        out.append(_parse(j, company))
    log.info("ashby.fetched", slug=slug, count=len(out))
    return out


def _parse(j: dict[str, Any], company: str) -> DiscoveredJob:
    posted = _parse_iso_date(j.get("publishedDate"))
    description = j.get("descriptionPlain") or _strip_html(j.get("descriptionHtml") or "")
    work_mode = "remote" if j.get("isRemote") else None
    salary = j.get("compensationTierSummary")
    return DiscoveredJob(
        title=j.get("title", "Untitled"),
        company=company,
        location=j.get("location"),
        work_mode=work_mode,
        salary_text=salary if isinstance(salary, str) else None,
        description_md=description[:8000] if description else None,
        posted_at=posted,
        apply_url=j.get("jobUrl"),
        source_provider="ashby",
    )


_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def _strip_html(html: str) -> str:
    return _WS_RE.sub(" ", _TAG_RE.sub(" ", html or "")).strip()


def _parse_iso_date(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
