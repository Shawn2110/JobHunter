from __future__ import annotations

import pytest
from pytest_httpx import HTTPXMock
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Profile, ProfileHandle
from app.services.handles import (
    HandleFetchError,
    fetch_github,
    fetch_leetcode,
    refresh_handle,
)


# ─── GitHub ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_fetch_github_returns_top_repos_and_languages(
    httpx_mock: HTTPXMock,
) -> None:
    httpx_mock.add_response(
        url="https://api.github.com/users/shawn",
        json={"name": "Shawn", "bio": "engineer", "public_repos": 12, "followers": 30},
    )
    httpx_mock.add_response(
        url="https://api.github.com/users/shawn/repos?sort=updated&per_page=30",
        json=[
            {"name": "alpha", "html_url": "u1", "stargazers_count": 50, "language": "Python", "description": "a"},
            {"name": "beta", "html_url": "u2", "stargazers_count": 200, "language": "Go", "description": "b"},
            {"name": "gamma", "html_url": "u3", "stargazers_count": 5, "language": "Python", "description": "c"},
        ],
    )
    signal = await fetch_github("shawn")
    assert signal["name"] == "Shawn"
    assert signal["public_repos"] == 12
    # Top repo by stars
    assert signal["top_repos"][0]["name"] == "beta"
    assert signal["top_repos"][0]["stars"] == 200
    # Languages deduped + sorted
    assert signal["languages"] == ["Go", "Python"]


# ─── LeetCode ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_fetch_leetcode_parses_graphql(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url="https://leetcode.com/graphql",
        json={
            "data": {
                "matchedUser": {
                    "username": "shawn",
                    "profile": {"realName": "Shawn", "ranking": 12345, "reputation": 50},
                    "submitStatsGlobal": {
                        "acSubmissionNum": [
                            {"difficulty": "Easy", "count": 100},
                            {"difficulty": "Medium", "count": 50},
                            {"difficulty": "Hard", "count": 5},
                        ]
                    },
                }
            }
        },
    )
    signal = await fetch_leetcode("shawn")
    assert signal["ranking"] == 12345
    assert signal["solved_by_difficulty"] == {"Easy": 100, "Medium": 50, "Hard": 5}


@pytest.mark.asyncio
async def test_fetch_leetcode_unknown_user_raises(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url="https://leetcode.com/graphql",
        json={"data": {"matchedUser": None}},
    )
    with pytest.raises(HandleFetchError, match="not found"):
        await fetch_leetcode("nobody")


# ─── refresh_handle dispatcher ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_refresh_handle_persists_signal(
    db_session: AsyncSession,
    httpx_mock: HTTPXMock,
) -> None:
    httpx_mock.add_response(
        url="https://api.github.com/users/x",
        json={"name": "X", "public_repos": 1, "followers": 0},
    )
    httpx_mock.add_response(
        url="https://api.github.com/users/x/repos?sort=updated&per_page=30",
        json=[],
    )

    profile = Profile(name="U", handles=[
        ProfileHandle(kind="github", username="x", url="https://github.com/x"),
    ])
    db_session.add(profile)
    await db_session.commit()
    handle = profile.handles[0]

    signal = await refresh_handle(handle, session=db_session)
    assert signal["name"] == "X"
    assert handle.last_signal_json == signal
    assert handle.last_fetched_at is not None


@pytest.mark.asyncio
async def test_refresh_handle_linkedin_does_not_fetch(
    db_session: AsyncSession,
    httpx_mock: HTTPXMock,
) -> None:
    """LinkedIn handle must NEVER trigger an outbound LinkedIn request."""
    profile = Profile(name="U", handles=[
        ProfileHandle(kind="linkedin", url="https://linkedin.com/in/foo"),
    ])
    db_session.add(profile)
    await db_session.commit()
    handle = profile.handles[0]

    signal = await refresh_handle(handle, session=db_session)
    assert "note" in signal
    assert "never fetches LinkedIn" in signal["note"]
    # pytest-httpx asserts no unexpected requests were made by default
    assert httpx_mock.get_requests() == []


@pytest.mark.asyncio
async def test_refresh_handle_swallows_http_errors(
    db_session: AsyncSession,
    httpx_mock: HTTPXMock,
) -> None:
    httpx_mock.add_response(
        url="https://api.github.com/users/x",
        status_code=500,
    )

    profile = Profile(name="U", handles=[
        ProfileHandle(kind="github", username="x", url="https://github.com/x"),
    ])
    db_session.add(profile)
    await db_session.commit()
    handle = profile.handles[0]

    signal = await refresh_handle(handle, session=db_session)
    assert "error" in signal
    # Despite the failure, the row was still updated
    assert handle.last_fetched_at is not None
