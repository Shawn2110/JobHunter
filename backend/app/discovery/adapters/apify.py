"""Apify-backed adapter for SPA portals where the keyless crawler can't
reach the rendered DOM.

Per ADR 0006: this is opt-in, paid, and explicitly excludes LinkedIn.
Supported portals: Naukri, Foundit, Wellfound. The user provides:
  - APIFY_API_TOKEN (required for any Apify call)
  - APIFY_NAUKRI_ACTOR / FOUNDIT_ACTOR / WELLFOUND_ACTOR (Actor IDs
    chosen from Apify's marketplace; user picks who they trust)

When a careers URL on one of these portals is supplied AND the
corresponding Actor is configured, this adapter runs the Actor
synchronously and parses results into DiscoveredJob records.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

import httpx
import structlog

from app.config import settings
from app.discovery.types import DiscoveredJob

log = structlog.get_logger("app.discovery.apify")

API_BASE = "https://api.apify.com/v2"


def detect_apify_portal(url: str) -> str | None:
    """Returns 'naukri' | 'foundit' | 'wellfound' | None.

    Mirrors `discovery.ats_providers.detect_ats` but for the SPA-only
    portals Apify covers. LinkedIn is intentionally absent.
    """
    if not url:
        return None
    host = url.lower()
    if "naukri.com" in host:
        return "naukri"
    if "foundit.in" in host:
        return "foundit"
    if "wellfound.com" in host:
        return "wellfound"
    return None


async def fetch_via_apify(
    *,
    portal: str,
    actor_id: str,
    url: str,
    api_token: str,
    client: httpx.AsyncClient | None = None,
) -> list[DiscoveredJob]:
    """Run an Apify Actor synchronously on a URL, return parsed jobs.

    Uses run-sync-get-dataset-items so we don't have to poll. Most
    job-scraper Actors accept a `startUrls` array and return a
    dataset of `{title, company, location, description, url, ...}`
    items. The exact shape varies per Actor — `_parse_item()` does a
    best-effort normalization.

    Slash in actor_id is encoded (Apify's URL form is `username~name`
    or `username/name`).
    """
    actor_path = actor_id.replace("/", "~")
    own_client = client is None
    if own_client:
        client = httpx.AsyncClient(
            timeout=180.0,  # Apify Actors can take a while
            headers={"User-Agent": "JobHunt/0.1 (self-hosted, local-only)"},
        )
    try:
        res = await client.post(
            f"{API_BASE}/acts/{actor_path}/run-sync-get-dataset-items",
            params={"token": api_token},
            json={"startUrls": [{"url": url}]},
        )
        if res.status_code == 404:
            log.warning("apify.actor_not_found", actor=actor_id)
            return []
        res.raise_for_status()
        items = res.json() if res.text.strip() else []
    finally:
        if own_client:
            await client.aclose()  # type: ignore[union-attr]

    if not isinstance(items, list):
        log.warning("apify.unexpected_shape", type=type(items).__name__)
        return []

    out: list[DiscoveredJob] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        out.append(_parse_item(item, portal))
    log.info("apify.fetched", actor=actor_id, portal=portal, count=len(out))
    return out


def _parse_item(item: dict[str, Any], portal: str) -> DiscoveredJob:
    """Best-effort normalize an Apify Actor's dataset item.

    Tries multiple common field names since each Actor shapes its
    output slightly differently. If your Actor uses non-standard
    keys, edit this function — most Actors use one of the patterns
    below.
    """
    title = _first(item, ["title", "jobTitle", "name", "position"]) or "Untitled"
    company = (
        _first(item, ["company", "companyName", "employer", "organization"])
        or _slug_to_company(portal)
    )
    location = _first(item, ["location", "jobLocation", "city", "place"])
    description = _first(
        item,
        ["description", "jobDescription", "details", "fullDescription"],
    )
    apply_url = (
        _first(item, ["url", "jobUrl", "applyUrl", "link"])
        or item.get("redirectUrl")
    )
    posted = _parse_date(_first(item, ["postedDate", "datePosted", "createdAt", "publishedDate"]))

    return DiscoveredJob(
        title=str(title),
        company=str(company),
        location=str(location) if location else None,
        work_mode=None,
        salary_text=_first(item, ["salary", "compensation", "pay"]),
        description_md=str(description)[:8000] if description else None,
        posted_at=posted,
        apply_url=str(apply_url) if apply_url else None,
        source_provider=f"apify_{portal}",
    )


def _first(item: dict[str, Any], keys: list[str]) -> Any:
    for k in keys:
        v = item.get(k)
        if v:
            return v
    return None


def _slug_to_company(portal: str) -> str:
    return f"({portal})"


def _parse_date(s: Any) -> datetime | None:
    if not s:
        return None
    if isinstance(s, datetime):
        return s
    if isinstance(s, str):
        # Try ISO 8601 first, then a few common alternatives
        for fmt in (None, "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
            try:
                if fmt is None:
                    return datetime.fromisoformat(re.sub(r"Z$", "+00:00", s))
                return datetime.strptime(s, fmt)
            except (ValueError, TypeError):
                continue
    return None


# ─── Convenience wrapper: portal-detect + fetch ──────────────────────────


async def fetch_for_url(
    url: str, client: httpx.AsyncClient | None = None
) -> list[DiscoveredJob]:
    """Detect portal from URL, route to the right Apify Actor.

    Returns [] when:
      - URL doesn't match a supported portal
      - Apify isn't configured (no token)
      - The portal's Actor ID isn't set
      - The Actor returns an error
    """
    portal = detect_apify_portal(url)
    if not portal:
        return []
    actor_id = settings.get_apify_actor(portal)
    if not actor_id or not settings.apify_api_token:
        log.info("apify.skipped", portal=portal, reason="not_configured")
        return []
    return await fetch_via_apify(
        portal=portal,
        actor_id=actor_id,
        url=url,
        api_token=settings.apify_api_token,
        client=client,
    )
