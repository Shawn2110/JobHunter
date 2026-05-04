"""Tests for the rich-payload save-job endpoint and back-compat shape."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Job, JobSource


@pytest.mark.asyncio
async def test_save_job_legacy_url_only(api_client: AsyncClient) -> None:
    """The legacy {url, title} shape still works for pages where the
    content script didn't run."""
    res = await api_client.post(
        "/extension/save-job",
        json={"url": "https://example.com/jobs/legacy", "title": "Engineer"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["id"] > 0
    assert body["apply_url"] == "https://example.com/jobs/legacy"


@pytest.mark.asyncio
async def test_save_job_rich_payload_persists_jd(
    api_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    res = await api_client.post(
        "/extension/save-job",
        json={
            "portal": "naukri",
            "title": "Senior Backend Engineer",
            "company": "Razorpay",
            "location": "Bengaluru, India",
            "description_md": "Build payment infrastructure used by 10M+ businesses.",
            "apply_url": "https://www.naukri.com/job-listings-senior-backend-razorpay-12345",
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["has_description"] is True
    assert body["company"] == "Razorpay"

    # Persisted with full JD text
    job = await db_session.get(Job, body["id"])
    assert job is not None
    assert job.title == "Senior Backend Engineer"
    assert job.company == "Razorpay"
    assert job.company_canonical == "razorpay"
    assert job.location == "Bengaluru, India"
    assert job.description_md is not None and "10M+ businesses" in job.description_md


@pytest.mark.asyncio
async def test_save_job_dedupes_on_apply_url(
    api_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Same apply_url saved twice → one Job, two JobSource rows."""
    url = "https://www.naukri.com/job-listings-engineer-acme-99999"
    payload = {
        "portal": "naukri",
        "title": "Engineer",
        "company": "Acme",
        "apply_url": url,
        "description_md": "Build stuff.",
    }
    first = await api_client.post("/extension/save-job", json=payload)
    second = await api_client.post("/extension/save-job", json=payload)
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert second.json()["duplicate"] is True

    # Two sightings recorded
    sources = (
        await db_session.execute(
            select(JobSource).where(JobSource.source_url == url)
        )
    ).scalars().all()
    assert len(sources) == 2


@pytest.mark.asyncio
async def test_save_job_records_portal_in_source_provider(
    api_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    res = await api_client.post(
        "/extension/save-job",
        json={
            "portal": "naukri",
            "title": "X",
            "company": "Y",
            "apply_url": "https://www.naukri.com/job-listings-x-y-1",
        },
    )
    assert res.status_code == 200
    sources = (
        await db_session.execute(select(JobSource).where(JobSource.job_id == res.json()["id"]))
    ).scalars().all()
    assert sources[0].source_provider == "extension_save_naukri"


@pytest.mark.asyncio
async def test_save_job_missing_url_returns_error(api_client: AsyncClient) -> None:
    res = await api_client.post("/extension/save-job", json={})
    body = res.json()
    assert "error" in body
