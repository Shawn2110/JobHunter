"""Tests for the v2 extension endpoints — live preview scoring and
the save-and-tailor handoff."""

from __future__ import annotations

import json

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.claude import ClaudeClient
from app.models import Profile, Resume


# ─── helpers ────────────────────────────────────────────────────────────────


def _stage(monkeypatch: pytest.MonkeyPatch, frozen_claude: ClaudeClient, payloads: list[dict]) -> None:
    """Stage a sequence of Claude responses."""
    response = frozen_claude._fake_messages.response  # type: ignore[attr-defined]
    fake_messages = frozen_claude._fake_messages  # type: ignore[attr-defined]
    counter = {"i": 0}

    async def staged(**kwargs):
        idx = counter["i"]
        counter["i"] = idx + 1
        payload = payloads[min(idx, len(payloads) - 1)]
        response.content[0].text = json.dumps(payload)
        fake_messages.calls.append(kwargs)
        return response

    monkeypatch.setattr(fake_messages, "create", staged)


_FAKE_KNOCKOUTS = {
    "knockouts": [
        {
            "question_text": "Are you authorized to work in India?",
            "type": "yes_no",
            "criterion": "in_work_auth",
            "required": True,
        }
    ]
}

_FAKE_TRUST_AI = {
    "verdict": "likely_real",
    "additional_signals_found": [],
    "ai_check_score": 80,
    "rationale_md": "Looks legit.",
}

_FAKE_FIT = {
    "skills_match": {"present": ["Python"], "missing": [], "score_required": "1/1"},
    "experience_verdict": "Matches.",
    "domain_match": "Strong.",
    "evidence_strength": "GitHub repos.",
    "knockout_risks": [],
    "verdict": "strong",
    "summary_md": "Strong match.",
}


_BASE_PAYLOAD = {
    "portal": "naukri",
    "title": "Senior Backend Engineer",
    "company": "Razorpay",
    "location": "Bengaluru",
    "description_md": "Build payment infrastructure used by 10M+ businesses.",
    "apply_url": "https://www.naukri.com/job-listings-12345",
}


# ─── /extension/score ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_score_full_flow_with_profile_and_resume(
    api_client: AsyncClient,
    db_session: AsyncSession,
    frozen_claude: ClaudeClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_session.add(Profile(name="U", target_seniority="senior"))
    db_session.add(
        Resume(
            version=1,
            is_master=True,
            parsed_json={"name": "U", "skills": ["Python"]},
        )
    )
    await db_session.commit()
    # Order: knockouts, trust AI, fit (3 calls)
    _stage(monkeypatch, frozen_claude, [_FAKE_KNOCKOUTS, _FAKE_TRUST_AI, _FAKE_FIT])

    res = await api_client.post("/extension/score", json=_BASE_PAYLOAD)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["has_profile"] is True
    assert body["has_resume"] is True
    assert body["fit"]["verdict"] == "strong"
    assert body["trust"]["verdict"] == "likely_real"
    assert len(body["knockouts"]) == 1
    assert body["notes"] == []


@pytest.mark.asyncio
async def test_score_no_profile_returns_partial_with_note(
    api_client: AsyncClient,
    frozen_claude: ClaudeClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without a profile, fit can't run — but trust + knockouts should
    still come back so the overlay isn't useless during first-time setup."""
    _stage(monkeypatch, frozen_claude, [_FAKE_KNOCKOUTS, _FAKE_TRUST_AI])

    res = await api_client.post("/extension/score", json=_BASE_PAYLOAD)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["has_profile"] is False
    assert body["has_resume"] is False
    assert body["fit"] is None
    assert body["trust"]["verdict"] == "likely_real"
    assert len(body["knockouts"]) == 1
    assert any("profile" in n.lower() for n in body["notes"])


@pytest.mark.asyncio
async def test_score_does_not_persist_anything(
    api_client: AsyncClient,
    db_session: AsyncSession,
    frozen_claude: ClaudeClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Critical: live preview must not pollute the DB with rows for
    jobs the user might immediately close."""
    from sqlalchemy import select
    from app.models import (
        FitAssessment,
        Job,
        JobRepostHistory,
        TrustAssessment,
    )

    db_session.add(Profile(name="U"))
    db_session.add(Resume(version=1, is_master=True, parsed_json={"name": "U"}))
    await db_session.commit()
    _stage(monkeypatch, frozen_claude, [_FAKE_KNOCKOUTS, _FAKE_TRUST_AI, _FAKE_FIT])

    res = await api_client.post("/extension/score", json=_BASE_PAYLOAD)
    assert res.status_code == 200

    for model in (Job, FitAssessment, TrustAssessment, JobRepostHistory):
        rows = (await db_session.execute(select(model))).scalars().all()
        assert rows == [], f"{model.__name__} should not have been persisted"


# ─── /extension/save-and-tailor ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_save_and_tailor_persists_and_returns_package_url(
    api_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    db_session.add(Profile(name="U"))
    db_session.add(Resume(version=1, is_master=True, parsed_json={"name": "U"}))
    await db_session.commit()

    res = await api_client.post("/extension/save-and-tailor", json=_BASE_PAYLOAD)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["job_id"] > 0
    assert body["package_url"].endswith(f"/jobs/{body['job_id']}/package")
    assert body["duplicate"] is False
    assert body["tailoring_status"] == "kicked_off"


@pytest.mark.asyncio
async def test_save_and_tailor_dedups_on_apply_url(
    api_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    first = await api_client.post("/extension/save-and-tailor", json=_BASE_PAYLOAD)
    second = await api_client.post("/extension/save-and-tailor", json=_BASE_PAYLOAD)
    assert first.json()["job_id"] == second.json()["job_id"]
    assert second.json()["duplicate"] is True


@pytest.mark.asyncio
async def test_save_and_tailor_warns_when_no_profile(
    api_client: AsyncClient,
) -> None:
    res = await api_client.post("/extension/save-and-tailor", json=_BASE_PAYLOAD)
    body = res.json()
    assert body["tailoring_status"] == "skipped_no_profile"


@pytest.mark.asyncio
async def test_save_and_tailor_warns_when_no_resume(
    api_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    db_session.add(Profile(name="U"))
    await db_session.commit()
    res = await api_client.post("/extension/save-and-tailor", json=_BASE_PAYLOAD)
    body = res.json()
    assert body["tailoring_status"] == "skipped_no_resume"
