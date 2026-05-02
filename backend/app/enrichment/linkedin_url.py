from __future__ import annotations

from dataclasses import dataclass

import httpx
import structlog

from app.config import settings

log = structlog.get_logger("app.enrichment.linkedin_url")


@dataclass(frozen=True)
class LinkedinCandidate:
    name: str | None
    role_hint: str | None
    linkedin_url: str
    source: str  # "brave" | "serper"


_BRAVE = "https://api.search.brave.com/res/v1/web/search"
_SERPER = "https://google.serper.dev/search"


async def discover_linkedin_urls(
    *,
    company: str,
    role_hint: str | None = None,
    top_k: int = 5,
) -> list[LinkedinCandidate]:
    """Find LinkedIn profile URLs via a public web search.

    Per Agent.md § 1: this is the ONLY acceptable LinkedIn-related
    operation. We get URLs; the user clicks them and visits manually.
    JobHunt itself never fetches linkedin.com pages.

    Picks Brave when configured, falls back to Serper, otherwise []
    with an info log.
    """
    role_part = f' "{role_hint}"' if role_hint else ""
    query = f'site:linkedin.com/in "{company}"{role_part}'

    if settings.brave_search_api_key:
        return await _via_brave(query, top_k)
    if settings.serper_api_key:
        return await _via_serper(query, top_k)
    log.info("linkedin_url.skipped", reason="no_search_provider_configured")
    return []


async def _via_brave(query: str, top_k: int) -> list[LinkedinCandidate]:
    headers = {
        "X-Subscription-Token": settings.brave_search_api_key or "",
        "Accept": "application/json",
    }
    params = {"q": query, "count": top_k}
    async with httpx.AsyncClient(timeout=15.0) as client:
        res = await client.get(_BRAVE, headers=headers, params=params)
        res.raise_for_status()
    body = res.json()
    out: list[LinkedinCandidate] = []
    for r in (body.get("web", {}).get("results") or [])[:top_k]:
        url = r.get("url", "")
        if "linkedin.com/in/" not in url:
            continue
        title = r.get("title", "") or ""
        # Brave often returns "Name - Role at Company | LinkedIn"
        name, _, _ = title.partition(" - ")
        role = title.partition(" - ")[2].partition(" | ")[0] or None
        out.append(LinkedinCandidate(
            name=name.strip() or None,
            role_hint=role.strip() if role else None,
            linkedin_url=url,
            source="brave",
        ))
    return out


async def _via_serper(query: str, top_k: int) -> list[LinkedinCandidate]:
    headers = {
        "X-API-KEY": settings.serper_api_key or "",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        res = await client.post(_SERPER, headers=headers, json={"q": query, "num": top_k})
        res.raise_for_status()
    body = res.json()
    out: list[LinkedinCandidate] = []
    for r in (body.get("organic") or [])[:top_k]:
        url = r.get("link", "")
        if "linkedin.com/in/" not in url:
            continue
        title = r.get("title", "")
        name = title.partition(" - ")[0]
        role = title.partition(" - ")[2].partition(" | ")[0] or None
        out.append(LinkedinCandidate(
            name=name.strip() or None,
            role_hint=role.strip() if role else None,
            linkedin_url=url,
            source="serper",
        ))
    return out
