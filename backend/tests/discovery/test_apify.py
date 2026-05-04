"""Tests for the Apify SPA-fallback adapter (Naukri / Foundit / Wellfound)."""

from __future__ import annotations

import pytest
from pytest_httpx import HTTPXMock

from app.discovery.adapters import apify


# ─── Portal detection ───────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "url, expected",
    [
        ("https://www.naukri.com/python-developer-jobs", "naukri"),
        ("https://www.foundit.in/srp/results?query=python", "foundit"),
        ("https://wellfound.com/jobs", "wellfound"),
        ("https://boards.greenhouse.io/postman", None),
        ("https://www.linkedin.com/jobs/", None),  # Excluded by design
        ("", None),
        ("not a url", None),
    ],
)
def test_detect_apify_portal(url: str, expected: str | None) -> None:
    assert apify.detect_apify_portal(url) == expected


# ─── Actor URL encoding ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_actor_id_with_slash_is_url_encoded(httpx_mock: HTTPXMock) -> None:
    """Apify accepts both 'user/name' and 'user~name'; we normalize
    to the URL-safe form."""
    httpx_mock.add_response(
        url="https://api.apify.com/v2/acts/epctex~naukri-scraper/run-sync-get-dataset-items?token=TEST",
        json=[],
    )
    out = await apify.fetch_via_apify(
        portal="naukri",
        actor_id="epctex/naukri-scraper",
        url="https://www.naukri.com/some-job",
        api_token="TEST",
    )
    assert out == []


# ─── Actor result parsing ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_fetch_via_apify_parses_standard_shape(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url="https://api.apify.com/v2/acts/epctex~naukri/run-sync-get-dataset-items?token=TEST",
        json=[
            {
                "title": "Senior Backend Engineer",
                "company": "Razorpay",
                "location": "Bengaluru, India",
                "description": "Build payment APIs.",
                "url": "https://www.naukri.com/job-listings-12345",
                "postedDate": "2026-04-30",
                "salary": "₹35-55 LPA",
            },
            {
                "jobTitle": "Engineer",
                "employer": "Acme",
                "city": "Mumbai",
                "details": "Stuff.",
                "applyUrl": "https://www.naukri.com/job-listings-67890",
            },
        ],
    )
    out = await apify.fetch_via_apify(
        portal="naukri",
        actor_id="epctex/naukri",
        url="https://www.naukri.com/python-jobs",
        api_token="TEST",
    )
    assert len(out) == 2
    assert out[0].title == "Senior Backend Engineer"
    assert out[0].company == "Razorpay"
    assert out[0].location == "Bengaluru, India"
    assert out[0].salary_text == "₹35-55 LPA"
    assert out[0].posted_at is not None
    assert out[0].source_provider == "apify_naukri"

    # Second item uses alternate field names — still parsed
    assert out[1].title == "Engineer"
    assert out[1].company == "Acme"
    assert out[1].apply_url == "https://www.naukri.com/job-listings-67890"


@pytest.mark.asyncio
async def test_fetch_via_apify_404_returns_empty(httpx_mock: HTTPXMock) -> None:
    """Misconfigured Actor ID → graceful empty list, not exception."""
    httpx_mock.add_response(
        url="https://api.apify.com/v2/acts/nonexistent~actor/run-sync-get-dataset-items?token=TEST",
        status_code=404,
    )
    out = await apify.fetch_via_apify(
        portal="naukri",
        actor_id="nonexistent/actor",
        url="https://www.naukri.com/job",
        api_token="TEST",
    )
    assert out == []


@pytest.mark.asyncio
async def test_fetch_via_apify_unexpected_shape_returns_empty(
    httpx_mock: HTTPXMock,
) -> None:
    httpx_mock.add_response(
        url="https://api.apify.com/v2/acts/x~y/run-sync-get-dataset-items?token=T",
        json={"unexpected": "object"},  # not a list
    )
    out = await apify.fetch_via_apify(
        portal="naukri", actor_id="x/y", url="https://www.naukri.com/x", api_token="T"
    )
    assert out == []


# ─── fetch_for_url config gating ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_fetch_for_url_skips_when_apify_token_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.config import settings

    monkeypatch.setattr(settings, "apify_api_token", None)
    out = await apify.fetch_for_url("https://www.naukri.com/python-jobs")
    assert out == []


@pytest.mark.asyncio
async def test_fetch_for_url_skips_when_actor_id_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.config import settings

    monkeypatch.setattr(settings, "apify_api_token", "TEST")
    monkeypatch.setattr(settings, "apify_naukri_actor", None)
    out = await apify.fetch_for_url("https://www.naukri.com/python-jobs")
    assert out == []


@pytest.mark.asyncio
async def test_fetch_for_url_skips_unsupported_portal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.config import settings

    monkeypatch.setattr(settings, "apify_api_token", "TEST")
    out = await apify.fetch_for_url("https://boards.greenhouse.io/postman")
    assert out == []


@pytest.mark.asyncio
async def test_fetch_for_url_skips_linkedin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Even with full Apify config, LinkedIn URLs must NOT route through
    Apify. Per ADR 0006."""
    from app.config import settings

    monkeypatch.setattr(settings, "apify_api_token", "TEST")
    out = await apify.fetch_for_url("https://www.linkedin.com/jobs/view/12345")
    assert out == []
