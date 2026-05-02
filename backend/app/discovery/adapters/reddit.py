from __future__ import annotations

import re
from datetime import datetime, timezone

import httpx

from app.discovery.adapters.base import DiscoveryAdapter
from app.discovery.types import DiscoveredJob, SearchInput

# Reddit job-search subreddits, India + global mix.
_SUBREDDITS = [
    "forhire",
    "remotework",
    "indiacareers",
    "developersindia",
    "JobSearch",
]

_HIRING_RE = re.compile(r"\[hiring\]|we'?re hiring|hiring\b", re.IGNORECASE)


class RedditAdapter(DiscoveryAdapter):
    """Reddit job-search subreddits via the public JSON API.

    Reddit's JSON endpoints work without auth at low volumes.
    We filter to "[Hiring]" / "we're hiring" posts and take title +
    selftext as the job description. No comment scraping — too noisy.
    """

    name = "reddit"
    source_kind = "founder_post"

    def is_configured(self) -> bool:
        # Reddit JSON works without keys; always considered configured.
        return True

    async def _fetch(self, query: SearchInput) -> list[DiscoveredJob]:
        out: list[DiscoveredJob] = []
        async with httpx.AsyncClient(
            timeout=10.0,
            headers={"User-Agent": "JobHunt/0.1 (self-hosted, local-only)"},
        ) as client:
            for sub in _SUBREDDITS:
                try:
                    res = await client.get(
                        f"https://www.reddit.com/r/{sub}/search.json",
                        params={
                            "q": query.role,
                            "restrict_sr": 1,
                            "sort": "new",
                            "t": "month",
                            "limit": 25,
                        },
                    )
                    if res.status_code != 200:
                        continue
                    data = res.json().get("data", {}).get("children", [])
                    for child in data:
                        d = child.get("data", {})
                        out.append(_parse(d, sub))
                except httpx.HTTPError:
                    continue
        # Filter to hiring posts only
        return [j for j in out if _HIRING_RE.search(j.title)]


def _parse(d: dict, sub: str) -> DiscoveredJob:
    posted = None
    ts = d.get("created_utc")
    if ts:
        try:
            posted = datetime.fromtimestamp(int(ts), tz=timezone.utc)
        except (ValueError, OSError):
            posted = None

    title = d.get("title", "Untitled")
    company_match = re.search(r"@\s*([A-Za-z0-9 &.]+)", title)
    company = company_match.group(1).strip() if company_match else f"r/{sub}"

    selftext = d.get("selftext") or ""
    return DiscoveredJob(
        title=title,
        company=company,
        location=None,
        work_mode=None,
        salary_text=None,
        description_md=selftext[:4000],
        posted_at=posted,
        apply_url=f"https://www.reddit.com{d.get('permalink', '')}",
        source_provider="reddit",
    )
