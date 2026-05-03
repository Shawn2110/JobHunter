"""End-to-end tests for the cover-letter and custom-questions endpoints."""

from __future__ import annotations

import json

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.claude import ClaudeClient
from app.models import Job, Profile, Resume


_FAKE_COVER_BRIEF = {
    "opener_angle": "Specific concrete reference.",
    "narrative_arc": "Three sentences mapping experience to role.",
    "closing_cta": "Open to a 30-min chat.",
    "tone": "warm-direct",
    "length_target_words": 220,
    "donts": ["leverage", "synergy"],
}
_FAKE_COVER_LETTER = {
    "body_md": "Body paragraph one.\n\nBody paragraph two.",
    "word_count": 6,
    "reasoning_md": "Why these choices.",
}


def _stage_responses(monkeypatch: pytest.MonkeyPatch, frozen_claude: ClaudeClient, payloads: list[dict]) -> None:
    """Make frozen_claude return `payloads[i]` on the i-th call.

    Resets call sequence each time it's called — calling _stage_responses
    twice in one test gives two independent staging windows. We don't
    chain through any previously-staged `create`; the staged function
    returns the response object directly to avoid monkeypatch chains
    leaking state across windows.
    """
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


async def _seed_profile_resume_job(db_session: AsyncSession) -> int:
    db_session.add(Profile(name="U", target_seniority="senior", salary_floor=4000000, salary_currency="INR", notice_period_days=60))
    db_session.add(
        Resume(
            version=1,
            is_master=True,
            parsed_json={
                "name": "U",
                "skills": ["Python", "FastAPI"],
                "experience": [
                    {"company": "Acme", "title": "Engineer", "bullets": ["Built things"]}
                ],
                "education": [{"institution": "BITS", "degree": "B.E."}],
            },
        )
    )
    job = Job(
        title="Senior Backend Engineer",
        company="Razorpay",
        company_canonical="razorpay",
        description_md="Build payment infrastructure.",
    )
    db_session.add(job)
    await db_session.commit()
    return job.id


# ─── Cover letter ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_cover_letter_returns_brief_and_artifact(
    api_client: AsyncClient,
    db_session: AsyncSession,
    frozen_claude: ClaudeClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job_id = await _seed_profile_resume_job(db_session)
    _stage_responses(monkeypatch, frozen_claude, [_FAKE_COVER_BRIEF, _FAKE_COVER_LETTER])

    res = await api_client.post(f"/tailoring/jobs/{job_id}/cover-letter")
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["brief"]["kind"] == "cover_letter"
    assert body["artifact"]["kind"] == "cover_letter"
    assert body["artifact"]["job_id"] == job_id
    assert body["artifact"]["content_md"].startswith("Body paragraph one.")
    assert body["artifact"]["content_json"]["word_count"] == 6


@pytest.mark.asyncio
async def test_cover_letter_requires_profile(
    api_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    job = Job(title="t", company="c", company_canonical="c")
    db_session.add(job)
    await db_session.commit()
    res = await api_client.post(f"/tailoring/jobs/{job.id}/cover-letter")
    assert res.status_code == 400
    assert "profile" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_cover_letter_404_for_unknown_job(api_client: AsyncClient) -> None:
    res = await api_client.post("/tailoring/jobs/9999/cover-letter")
    assert res.status_code == 404


# ─── Custom questions ──────────────────────────────────────────────────────


_FAKE_CQ = {"answer_md": "A specific concrete answer.", "word_count": 4}


@pytest.mark.asyncio
async def test_create_custom_answers_runs_all_5_by_default(
    api_client: AsyncClient,
    db_session: AsyncSession,
    frozen_claude: ClaudeClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job_id = await _seed_profile_resume_job(db_session)
    # 5 default questions → 5 Claude calls; same response shape for each
    _stage_responses(monkeypatch, frozen_claude, [_FAKE_CQ] * 5)

    res = await api_client.post(
        f"/tailoring/jobs/{job_id}/custom-questions",
        json={},
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert len(body["answers"]) == 5
    keys = {a["key"] for a in body["answers"]}
    assert {"why_this_company", "why_this_role", "why_leaving", "biggest_project", "salary_expectations"} == keys
    assert body["artifact_id"] > 0


@pytest.mark.asyncio
async def test_create_custom_answers_subset_via_keys(
    api_client: AsyncClient,
    db_session: AsyncSession,
    frozen_claude: ClaudeClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job_id = await _seed_profile_resume_job(db_session)
    _stage_responses(monkeypatch, frozen_claude, [_FAKE_CQ] * 2)

    res = await api_client.post(
        f"/tailoring/jobs/{job_id}/custom-questions",
        json={"keys": ["why_this_company", "salary_expectations"]},
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert len(body["answers"]) == 2
    assert {a["key"] for a in body["answers"]} == {"why_this_company", "salary_expectations"}


# ─── List artifacts for a job (any kind) ────────────────────────────────────


@pytest.mark.asyncio
async def test_list_job_artifacts_includes_all_kinds(
    api_client: AsyncClient,
    db_session: AsyncSession,
    frozen_claude: ClaudeClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job_id = await _seed_profile_resume_job(db_session)

    # Create a cover letter
    _stage_responses(monkeypatch, frozen_claude, [_FAKE_COVER_BRIEF, _FAKE_COVER_LETTER])
    cl_res = await api_client.post(f"/tailoring/jobs/{job_id}/cover-letter")
    assert cl_res.status_code == 201

    # Create custom answers (1 question for speed)
    _stage_responses(monkeypatch, frozen_claude, [_FAKE_CQ])
    cq_res = await api_client.post(
        f"/tailoring/jobs/{job_id}/custom-questions",
        json={"keys": ["why_this_company"]},
    )
    assert cq_res.status_code == 201

    res = await api_client.get(f"/tailoring/jobs/{job_id}/artifacts")
    assert res.status_code == 200
    body = res.json()
    kinds = {a["kind"] for a in body}
    assert "cover_letter" in kinds
    assert "custom_answers" in kinds
