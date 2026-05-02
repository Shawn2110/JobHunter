"""End-to-end test for the CareersPageAdapter dispatch logic.

Confirms that pasting a Greenhouse / Lever / Ashby URL routes to the
right ATS adapter (no JSON-LD parsing fallback), and that company-
direct URLs fall through to JSON-LD parsing.
"""

from __future__ import annotations

import pytest
from pytest_httpx import HTTPXMock

from app.discovery.adapters.careers_page import CareersPageAdapter, crawl_urls
from app.discovery.types import SearchInput


@pytest.mark.asyncio
async def test_greenhouse_url_routes_to_ats_adapter(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url="https://boards-api.greenhouse.io/v1/boards/postman/jobs?content=true",
        json={
            "jobs": [
                {
                    "id": 1,
                    "title": "Backend Engineer",
                    "absolute_url": "u",
                    "location": {"name": "Remote"},
                    "updated_at": "2026-04-15T00:00:00Z",
                    "content": "x",
                }
            ]
        },
    )
    out = await crawl_urls(["https://boards.greenhouse.io/postman"])
    assert len(out) == 1
    assert out[0].source_provider == "greenhouse"


@pytest.mark.asyncio
async def test_company_url_falls_back_to_jsonld(httpx_mock: HTTPXMock) -> None:
    html = """
    <html><body>
    <script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@type": "JobPosting",
      "title": "Director of Engineering",
      "hiringOrganization": {"name": "Acme Co"},
      "jobLocation": {"address": {"addressLocality": "Bengaluru"}},
      "datePosted": "2026-04-01"
    }
    </script>
    </body></html>
    """
    httpx_mock.add_response(url="https://acme.example/careers", text=html)
    out = await crawl_urls(["https://acme.example/careers"])
    assert len(out) == 1
    assert out[0].title == "Director of Engineering"
    assert out[0].company == "Acme Co"
    assert out[0].source_provider == "careers_page"


@pytest.mark.asyncio
async def test_adapter_skips_non_url_locations(httpx_mock: HTTPXMock) -> None:
    """When SearchInput.locations contains a city name (not a URL),
    the adapter returns []. No HTTP calls."""
    adapter = CareersPageAdapter()
    out = await adapter._fetch(  # noqa: SLF001
        SearchInput(role="x", locations=["Bengaluru", "Mumbai"])
    )
    assert out == []
    assert httpx_mock.get_requests() == []
