"""Fixture tests for the three keyless ATS adapters.

Each test uses pytest-httpx to mock the public board API response,
then asserts the adapter parses it into well-formed DiscoveredJob
records. No live network — these are fast and deterministic.
"""

from __future__ import annotations

import pytest
from pytest_httpx import HTTPXMock

from app.discovery.adapters import ashby, greenhouse, lever


# ─── Greenhouse ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_greenhouse_parses_jobs(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url="https://boards-api.greenhouse.io/v1/boards/postman/jobs?content=true",
        json={
            "jobs": [
                {
                    "id": 1,
                    "title": "Senior Backend Engineer",
                    "absolute_url": "https://boards.greenhouse.io/postman/jobs/1",
                    "location": {"name": "Bengaluru, India"},
                    "updated_at": "2026-04-15T12:00:00Z",
                    "content": "<p>Build payment APIs.</p><ul><li>Python</li></ul>",
                    "departments": [{"name": "Engineering"}],
                },
                {
                    "id": 2,
                    "title": "Recruiter",
                    "absolute_url": "https://boards.greenhouse.io/postman/jobs/2",
                    "location": {"name": "Remote"},
                    "updated_at": "2026-04-10T00:00:00Z",
                    "content": "Hire engineers.",
                },
            ]
        },
    )
    out = await greenhouse.fetch_for_slug("postman")
    assert len(out) == 2
    assert out[0].title == "Senior Backend Engineer"
    assert out[0].company == "Postman"
    assert out[0].location == "Bengaluru, India"
    assert out[0].source_provider == "greenhouse"
    assert out[0].apply_url == "https://boards.greenhouse.io/postman/jobs/1"
    # HTML stripped from content
    assert out[0].description_md is not None
    assert "<p>" not in out[0].description_md
    assert "Build payment APIs" in out[0].description_md


@pytest.mark.asyncio
async def test_greenhouse_unknown_slug_returns_empty(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url="https://boards-api.greenhouse.io/v1/boards/nope/jobs?content=true",
        status_code=404,
    )
    assert await greenhouse.fetch_for_slug("nope") == []


# ─── Lever ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_lever_parses_jobs(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url="https://api.lever.co/v0/postings/spotify?mode=json",
        json=[
            {
                "id": "abc",
                "text": "Backend Engineer",
                "createdAt": 1715212800000,  # 2024-05-09 UTC
                "categories": {
                    "commitment": "Full-time",
                    "department": "Engineering",
                    "location": "Stockholm, Sweden",
                    "team": "Platform",
                },
                "hostedUrl": "https://jobs.lever.co/spotify/abc",
                "applyUrl": "https://jobs.lever.co/spotify/abc/apply",
                "descriptionPlain": "Build streaming infrastructure.",
            }
        ],
    )
    out = await lever.fetch_for_slug("spotify")
    assert len(out) == 1
    j = out[0]
    assert j.title == "Backend Engineer"
    assert j.company == "Spotify"
    assert j.location == "Stockholm, Sweden"
    assert j.source_provider == "lever"
    assert j.posted_at is not None
    assert j.apply_url == "https://jobs.lever.co/spotify/abc"


@pytest.mark.asyncio
async def test_lever_remote_detection(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url="https://api.lever.co/v0/postings/acme?mode=json",
        json=[
            {
                "id": "1",
                "text": "Engineer",
                "categories": {"location": "Remote — Worldwide"},
                "hostedUrl": "u",
                "descriptionPlain": "x",
            }
        ],
    )
    out = await lever.fetch_for_slug("acme")
    assert out[0].work_mode == "remote"


@pytest.mark.asyncio
async def test_lever_unknown_slug_returns_empty(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url="https://api.lever.co/v0/postings/nope?mode=json",
        status_code=404,
    )
    assert await lever.fetch_for_slug("nope") == []


# ─── Ashby ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ashby_parses_jobs(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url="https://api.ashbyhq.com/posting-api/job-board/linear?includeCompensation=true",
        json={
            "title": "Linear",
            "jobs": [
                {
                    "id": "x",
                    "title": "Senior Engineer",
                    "department": "Engineering",
                    "team": "Core",
                    "isListed": True,
                    "isRemote": True,
                    "location": "Anywhere",
                    "employmentType": "FullTime",
                    "publishedDate": "2026-04-20T00:00:00Z",
                    "jobUrl": "https://jobs.ashbyhq.com/linear/x",
                    "descriptionHtml": "<p>Build the editor.</p>",
                    "compensationTierSummary": "$200K – $260K",
                },
                {
                    "id": "y",
                    "title": "Hidden",
                    "isListed": False,  # filtered out
                    "jobUrl": "u",
                },
            ],
        },
    )
    out = await ashby.fetch_for_slug("linear")
    assert len(out) == 1
    j = out[0]
    assert j.title == "Senior Engineer"
    assert j.company == "Linear"
    assert j.work_mode == "remote"
    assert j.salary_text == "$200K – $260K"
    assert j.description_md is not None and "Build the editor" in j.description_md
    assert j.apply_url == "https://jobs.ashbyhq.com/linear/x"


@pytest.mark.asyncio
async def test_ashby_unknown_slug_returns_empty(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url="https://api.ashbyhq.com/posting-api/job-board/nope?includeCompensation=true",
        status_code=404,
    )
    assert await ashby.fetch_for_slug("nope") == []
