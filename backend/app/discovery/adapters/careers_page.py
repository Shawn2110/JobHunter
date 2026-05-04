from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime
from typing import Any

import httpx
import structlog

from app.discovery.adapters import apify, ashby, greenhouse, lever
from app.discovery.adapters.base import DiscoveryAdapter
from app.discovery.ats_providers import detect_ats
from app.discovery.types import DiscoveredJob, SearchInput

log = structlog.get_logger("app.discovery.careers_page")

# Polite per-domain rate limit: 1 request per 5 seconds per host.
_RATE_LIMIT_SECONDS = 5
_last_request_at: dict[str, float] = {}
_rate_lock = asyncio.Lock()


_JOB_POSTING_RE = re.compile(
    r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>',
    re.DOTALL | re.IGNORECASE,
)


async def _polite_wait(host: str) -> None:
    async with _rate_lock:
        now = asyncio.get_running_loop().time()
        last = _last_request_at.get(host)
        if last is not None and now - last < _RATE_LIMIT_SECONDS:
            await asyncio.sleep(_RATE_LIMIT_SECONDS - (now - last))
        _last_request_at[host] = asyncio.get_running_loop().time()


class CareersPageAdapter(DiscoveryAdapter):
    """Crawls user-supplied careers URLs.

    Dispatches by ATS provider:
    - Greenhouse / Lever / Ashby URLs → public board API (keyless,
      ToS-clean, returns the same data the live page renders).
    - Anything else → falls back to JSON-LD parsing of the rendered
      page. Works for company-direct careers pages that ship
      `application/ld+json` JobPosting blocks; doesn't work for
      SPAs (Naukri, Foundit, Wellfound, etc. — those would need
      Playwright, which is a separate optional path).

    URLs come from `SearchInput.locations` for ad-hoc crawls; the
    nightly worker iterates `WatchlistCompany.careers_url` directly.
    """

    name = "careers_page"
    source_kind = "careers_page"

    def is_configured(self) -> bool:
        return True  # Always available — fetch decides per-URL

    async def _fetch(self, query: SearchInput) -> list[DiscoveredJob]:
        urls = [loc for loc in (query.locations or []) if loc.startswith("http")]
        if not urls:
            return []
        return await crawl_urls(urls)


async def crawl_urls(urls: list[str]) -> list[DiscoveredJob]:
    """Fan out across URLs, dispatching each to the right backend."""
    out: list[DiscoveredJob] = []
    async with httpx.AsyncClient(
        timeout=20.0,
        headers={"User-Agent": "JobHunt/0.1 (self-hosted, local-only)"},
        follow_redirects=True,
    ) as client:
        for url in urls:
            host = url.split("/")[2] if "//" in url else url
            await _polite_wait(host)

            ats = detect_ats(url)
            if ats:
                provider, slug = ats
                try:
                    if provider == "greenhouse":
                        jobs = await greenhouse.fetch_for_slug(slug, client=client)
                    elif provider == "lever":
                        jobs = await lever.fetch_for_slug(slug, client=client)
                    elif provider == "ashby":
                        jobs = await ashby.fetch_for_slug(slug, client=client)
                    else:
                        jobs = []
                    out.extend(jobs)
                except httpx.HTTPError as e:
                    log.warning(
                        "careers_page.ats_error",
                        provider=provider,
                        slug=slug,
                        error=type(e).__name__,
                    )
                continue

            # Apify fallback for SPA portals (Naukri / Foundit / Wellfound).
            # No-op if Apify isn't configured. LinkedIn is intentionally
            # excluded (per ADR 0006); detect_apify_portal won't match.
            if apify.detect_apify_portal(url):
                try:
                    apify_jobs = await apify.fetch_for_url(url, client=client)
                    out.extend(apify_jobs)
                except httpx.HTTPError as e:
                    log.warning(
                        "careers_page.apify_error",
                        url=url,
                        error=type(e).__name__,
                    )
                continue

            # Fallback: plain GET + JSON-LD parsing
            html = await _fetch_html(client, url)
            if not html:
                continue
            postings = _parse_jsonld(html)
            company_fallback = host.split(".")[-2] if "." in host else host
            for p in postings:
                out.append(_job_from_jsonld(p, company_fallback))
            log.info(
                "careers_page.crawled_jsonld",
                url=url,
                postings=len(postings),
            )
    return out


async def _fetch_html(client: httpx.AsyncClient, url: str) -> str | None:
    try:
        res = await client.get(url)
        if res.status_code >= 400:
            return None
        return res.text
    except httpx.HTTPError:
        return None


def _parse_jsonld(html: str) -> list[dict[str, Any]]:
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
            parts = [
                addr.get(k)
                for k in ("addressLocality", "addressRegion", "addressCountry")
            ]
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
