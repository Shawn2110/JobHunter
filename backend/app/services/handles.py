from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import ProfileHandle

log = structlog.get_logger("app.services.handles")


class HandleFetchError(Exception):
    """Raised when an external handle fetch fails."""


# ─── Per-kind fetchers ──────────────────────────────────────────────────────
# Each fetcher returns a small "signal" dict that's stored on
# ProfileHandle.last_signal_json. Keep the shape minimal — we want
# JD-relevant signals, not full profile dumps.


async def fetch_github(username: str, token: str | None = None) -> dict[str, Any]:
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    async with httpx.AsyncClient(headers=headers, timeout=10.0) as client:
        user_res = await client.get(f"https://api.github.com/users/{username}")
        user_res.raise_for_status()
        repos_res = await client.get(
            f"https://api.github.com/users/{username}/repos",
            params={"sort": "updated", "per_page": 30},
        )
        repos_res.raise_for_status()

    user = user_res.json()
    repos = repos_res.json()
    # Sort by stars and take top 5.
    top = sorted(repos, key=lambda r: r.get("stargazers_count", 0), reverse=True)[:5]
    languages = sorted(
        {r["language"] for r in repos if r.get("language")},
    )

    return {
        "name": user.get("name"),
        "bio": user.get("bio"),
        "public_repos": user.get("public_repos"),
        "followers": user.get("followers"),
        "languages": languages,
        "top_repos": [
            {
                "name": r["name"],
                "url": r["html_url"],
                "stars": r.get("stargazers_count", 0),
                "language": r.get("language"),
                "description": r.get("description"),
            }
            for r in top
        ],
    }


_LEETCODE_QUERY = """
query getUserProfile($username: String!) {
  matchedUser(username: $username) {
    username
    profile { realName, ranking, reputation }
    submitStatsGlobal {
      acSubmissionNum { difficulty, count }
    }
  }
}
"""


async def fetch_leetcode(username: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=10.0) as client:
        res = await client.post(
            "https://leetcode.com/graphql",
            json={"query": _LEETCODE_QUERY, "variables": {"username": username}},
            headers={"Content-Type": "application/json"},
        )
        res.raise_for_status()
    body = res.json()
    user = (body.get("data") or {}).get("matchedUser")
    if not user:
        raise HandleFetchError(f"LeetCode user not found: {username}")
    profile = user.get("profile") or {}
    stats = (user.get("submitStatsGlobal") or {}).get("acSubmissionNum") or []
    return {
        "username": user.get("username"),
        "real_name": profile.get("realName"),
        "ranking": profile.get("ranking"),
        "reputation": profile.get("reputation"),
        "solved_by_difficulty": {
            row.get("difficulty"): row.get("count") for row in stats
        },
    }


async def fetch_kaggle(username: str, url: str) -> dict[str, Any]:
    """Kaggle has no public profile API without OAuth — verify URL is reachable."""
    return await _verify_url(url, kind="kaggle", username=username)


async def fetch_linkedin(_username: str, url: str) -> dict[str, Any]:
    """Per Agent.md, JobHunt never fetches LinkedIn pages.

    The handle is stored as a URL the user clicks manually. This fetcher
    returns a stub signal documenting that fact.
    """
    return {
        "url": url,
        "note": (
            "LinkedIn URL stored. JobHunt never fetches LinkedIn pages "
            "per Agent.md § 1; the user opens this URL manually."
        ),
    }


async def fetch_portfolio(_username: str | None, url: str) -> dict[str, Any]:
    return await _verify_url(url, kind="portfolio")


async def _verify_url(url: str, kind: str, **extra: Any) -> dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
            res = await client.head(url)
        return {"url": url, "kind": kind, "reachable": res.status_code < 500, **extra}
    except httpx.HTTPError as e:
        return {"url": url, "kind": kind, "reachable": False, "error": str(e), **extra}


# ─── Dispatcher ─────────────────────────────────────────────────────────────


async def refresh_handle(
    handle: ProfileHandle, session: AsyncSession | None = None
) -> dict[str, Any]:
    """Refresh `handle.last_signal_json` and `last_fetched_at` in place.

    Picks the right fetcher based on `handle.kind`. Errors are caught
    and stored as `{"error": ...}` so the UI can surface them without
    failing the whole refresh batch.
    """
    kind = handle.kind
    username = handle.username or ""
    url = handle.url

    try:
        if kind == "github":
            if not username:
                raise HandleFetchError("GitHub handle is missing username")
            signal = await fetch_github(username, settings.github_token)
        elif kind == "leetcode":
            if not username:
                raise HandleFetchError("LeetCode handle is missing username")
            signal = await fetch_leetcode(username)
        elif kind == "kaggle":
            signal = await fetch_kaggle(username, url)
        elif kind == "linkedin":
            signal = await fetch_linkedin(username, url)
        elif kind == "portfolio":
            signal = await fetch_portfolio(username, url)
        else:
            signal = {"error": f"Unknown handle kind: {kind!r}"}
    except (httpx.HTTPError, HandleFetchError) as e:
        signal = {"error": f"{type(e).__name__}: {e}"}
        log.warning("handle.fetch_failed", kind=kind, username=username, error=str(e))

    handle.last_signal_json = signal
    handle.last_fetched_at = datetime.now(timezone.utc)
    if session is not None:
        await session.commit()
        await session.refresh(handle)
    return signal
