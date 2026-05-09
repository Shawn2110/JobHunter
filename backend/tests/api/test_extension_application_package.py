"""Tests for /extension/application-package — the autofill bundle.

The content script's autofill bar reads this; field names here are
treated as a contract by the extension. When you add or rename a
field, update content.js's autofill() field list to match.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Profile, Resume


@pytest.mark.asyncio
async def test_application_package_empty_when_no_profile(
    api_client: AsyncClient,
) -> None:
    """No profile set up yet → both keys present but null."""
    res = await api_client.get("/extension/application-package")
    assert res.status_code == 200
    body = res.json()
    assert body["profile"] is None
    assert body["resume_summary"] is None


@pytest.mark.asyncio
async def test_application_package_returns_contact_and_current_employment(
    api_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """All autofill-relevant fields are returned when profile + master
    resume are present. The extension's autofill() relies on these
    exact keys."""
    profile = Profile(name="Test User", target_seniority="senior")
    resume = Resume(
        version=1,
        is_master=True,
        parsed_json={
            "name": "Test User",
            "email": "test@example.com",
            "phone": "+91 90000 00000",
            "location": "Bengaluru, India",
            "links": [
                {"kind": "linkedin", "url": "https://linkedin.com/in/test"},
                {"kind": "github", "url": "https://github.com/test"},
            ],
            "experience": [
                {"company": "Razorpay", "title": "Senior Engineer",
                 "start_date": "2023", "end_date": None, "bullets": []},
                {"company": "Acme", "title": "Engineer",
                 "start_date": "2020", "end_date": "2023", "bullets": []},
            ],
            "summary": "Backend engineer working on payments.",
            "skills": ["Python", "Postgres"],
        },
    )
    db_session.add_all([profile, resume])
    await db_session.commit()

    res = await api_client.get("/extension/application-package")
    assert res.status_code == 200
    body = res.json()

    p = body["profile"]
    assert p["name"] == "Test User"
    assert p["email"] == "test@example.com"
    assert p["phone"] == "+91 90000 00000"
    assert p["location"] == "Bengaluru, India"
    assert p["current_title"] == "Senior Engineer"
    assert p["current_company"] == "Razorpay"
    assert any(l["kind"] == "linkedin" for l in p["links"])
    assert any(l["kind"] == "github" for l in p["links"])

    s = body["resume_summary"]
    assert s["summary"] == "Backend engineer working on payments."
    assert "Python" in s["skills"]


@pytest.mark.asyncio
async def test_application_package_handles_missing_experience(
    api_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """A resume without experience entries → current_title /
    current_company are null, not a KeyError."""
    profile = Profile(name="Test User")
    resume = Resume(
        version=1,
        is_master=True,
        parsed_json={
            "name": "Test User",
            "email": "test@example.com",
            "experience": [],
            "skills": [],
        },
    )
    db_session.add_all([profile, resume])
    await db_session.commit()

    res = await api_client.get("/extension/application-package")
    assert res.status_code == 200
    p = res.json()["profile"]
    assert p["current_title"] is None
    assert p["current_company"] is None
    assert p["location"] is None
