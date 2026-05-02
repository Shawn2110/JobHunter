from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import structlog
import yaml

from app.config import settings
from app.discovery.adapters.base import DiscoveryAdapter
from app.discovery.types import DiscoveredJob, SearchInput

log = structlog.get_logger("app.discovery.careers_page")

_SELECTORS_PATH = Path(__file__).resolve().parent.parent / "selectors.yaml"

# Polite per-domain rate limit: 1 request per 5 seconds per domain
_RATE_LIMIT_SECONDS = 5
_last_request_at: dict[str, float] = {}
_rate_lock = asyncio.Lock()

_JOB_POSTING_RE = re.compile(
    r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>',
    re.DOTALL | re.IGNORECASE,
)


def load_selectors() -> dict[str, dict[str, str]]:
    raw = yaml.safe_load(_SELECTORS_PATH.read_text(encoding="utf-8"))
    return raw.get("domains", {})


async def _polite_wait(host: str) -> None:
    async with _rate_lock:
        now = asyncio.get_running_loop().time()
        last = _last_request_at.get(host)
        if last is not None and now - last < _RATE_LIMIT_SECONDS:
            await asyncio.sleep(_RATE_LIMIT_SECONDS - (now - last))
        _last_request_at[host] = asyncio.get_running_loop().time()


def _parse_jsonld(html: str) -> list[dict[str, Any]]:
    """Pull JobPosting JSON-LD blocks out of HTML. Most modern ATS
    expose at least the title + description this way."""
    out: list[dict[str, Any]] = []
    for match in _JOB_POSTING_RE.finditer(html):
        try:
            data = json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            continue
        items = data if isinstance(data, list) else [data]
        for item in items:
            if not isinstance(item, dict):
                continue
            if item.get("@type") in ("JobPosting", "Job"):
                out.append(item)
    return out


def _parse_iso_date(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _job_from_jsonld(item: dict[str, Any], company_fallback: str) -> DiscoveredJob:
    org = item.get("hiringOrganization") or {}
    company = (org.get("name") if isinstance(org, dict) else None) or company_fallback
    location = None
    loc = item.get("jobLocation")
    if isinstance(loc, dict):
        addr = loc.get("address") or {}
        if isinstance(addr, dict):
            parts = [addr.get(k) for k in ("addressLocality", "addressRegion", "addressCountry")]
            location = ", ".join(p for p in parts if p) or None
    return DiscoveredJob(
        title=item.get("title", "Untitled"),
        company=company,
        location=location,
        work_mode="remote" if item.get("jobLocationType") == "TELECOMMUTE" else None,
        salary_text=str(item.get("baseSalary")) if item.get("baseSalary") else None,
        description_md=re.sub(r"<[^>]+>", " ", str(item.get("description", "")))[:8000],
        posted_at=_parse_iso_date(item.get("datePosted")),
        apply_url=item.get("url") or item.get("applicationContact", {}).get("url"),
        source_provider="careers_page",
    )


class CareersPageAdapter(DiscoveryAdapter):
    """Careers-page crawler.

    Iterates a user-configured list of company URLs (passed via the
    SearchInput.locations field as a temporary v1 hack — we'll wire
    in proper Watchlist usage in Phase 9). Tries Firecrawl when
    configured for SPA pages; falls back to plain httpx for pages
    that ship JobPosting JSON-LD on first paint.

    Per Architecture § 5.1: respects robots.txt (TODO follow-up) and
    rate-limits at 1 request per 5 seconds per domain.
    """

    name = "careers_page"
    source_kind = "careers_page"

    def is_configured(self) -> bool:
        # Configured iff at least one URL is supplied at call time. The
        # orchestrator may bypass adapters that return [] anyway, so we
        # always say yes here and let _fetch decide.
        return True

    async def _fetch(self, query: SearchInput) -> list[DiscoveredJob]:
        # v1: treat each entry in locations that LOOKS like a URL as a
        # careers-page URL to crawl. Real Watchlist integration lands
        # in Phase 9.
        urls = [loc for loc in (query.locations or []) if loc.startswith("http")]
        if not urls:
            return []

        out: list[DiscoveredJob] = []
        for url in urls:
            host = url.split("/")[2] if "//" in url else url
            await _polite_wait(host)
            html = await _fetch_html(url)
            if not html:
                continue
            postings = _parse_jsonld(html)
            company_fallback = host.split(".")[-2] if "." in host else host
            for p in postings:
                out.append(_job_from_jsonld(p, company_fallback))
            log.info(
                "careers_page.crawled",
                url=url,
                postings=len(postings),
            )
        return out


async def _fetch_html(url: str) -> str | None:
    """Plain GET. Firecrawl integration is a follow-up (paid service).

    Returns None on any error so a single bad URL never poisons the
    whole orchestrator run.
    """
    try:
        async with httpx.AsyncClient(
            timeout=15.0,
            headers={"User-Agent": "JobHunt/0.1 (self-hosted, local-only)"},
            follow_redirects=True,
        ) as client:
            res = await client.get(url)
            if res.status_code >= 400:
                return None
            return res.text
    except httpx.HTTPError:
        return None
