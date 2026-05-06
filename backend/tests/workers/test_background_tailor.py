"""Tests for the v2.x background-tailor worker.

The worker opens its own SessionLocal (since the request session has
already closed by the time it runs) and instantiates ClaudeClient
directly from settings. Tests stub both: replace SessionLocal so
tests use the in-memory db_session, and replace ClaudeClient so we
don't hit the live API.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Job, Profile, Resume, TailoredArtifact, TailoringBrief
from app.workers import background_tailor


_FAKE_BRIEF = {
    "positioning": "Position as senior python engineer.",
    "vocabulary_shifts": [],
    "keywords_truthfully_supported": [],
    "keywords_to_omit_with_reason": [],
    "emphasis_changes": "Lead with payment work.",
    "de_emphasis_changes": "Cut older roles.",
    "ats_family_specific_notes": "Greenhouse — modern parsing.",
    "truthfulness_boundaries": "No management claims.",
    "knockout_warnings": [],
}

_FAKE_REWRITTEN = {
    "name": "Test User",
    "email": "test@example.com",
    "phone": None,
    "location": None,
    "summary": "Backend engineer.",
    "experience": [
        {
            "company": "Acme",
            "title": "Engineer",
            "start_date": "2022",
            "end_date": "2024",
            "location": None,
            "bullets": ["Built things"],
        }
    ],
    "education": [{"institution": "BITS", "degree": "B.E.", "field": "CS",
                   "start_date": None, "end_date": None, "gpa": None}],
    "skills": ["Python"],
    "projects": [],
    "links": [],
    "diff_summary": ["Reordered bullets"],
}

_FAKE_COVER_BRIEF = {
    "opener_angle": "Specific reference.",
    "narrative_arc": "Three sentences.",
    "closing_cta": "Open to a 30-min chat.",
    "tone": "warm-direct",
    "length_target_words": 220,
    "donts": ["leverage", "synergy"],
}
_FAKE_COVER_LETTER = {
    "body_md": "Body.",
    "word_count": 1,
    "reasoning_md": "Why.",
}

_FAKE_CQ = {"answer_md": "Concrete answer.", "word_count": 2}

_FAKE_KNOCKOUTS = {"knockouts": []}


def _staged_create(payloads: list[dict]):
    """Build a fake AsyncAnthropic.messages.create that returns the
    next staged JSON payload on each call."""
    counter = {"i": 0}

    async def create(**kwargs):
        idx = counter["i"]
        counter["i"] = idx + 1
        payload = payloads[min(idx, len(payloads) - 1)]
        return SimpleNamespace(
            content=[SimpleNamespace(text=json.dumps(payload))],
            usage=SimpleNamespace(input_tokens=10, output_tokens=20),
            model="claude-sonnet-4-6",
            id="msg_test",
            role="assistant",
            stop_reason="end_turn",
        )

    return create


def _stub_session_local(monkeypatch: pytest.MonkeyPatch, session: AsyncSession) -> None:
    """Make `async with SessionLocal()` yield the test session.

    We can't use the test fixture session directly inside the worker
    because it closes the session in `__aexit__`, which would break
    the rest of the test. Wrap it in a forwarder that's a no-op on
    enter/exit but yields the same session.
    """
    class _Forwarder:
        async def __aenter__(self_):  # noqa: ARG002
            return session

        async def __aexit__(self_, *args):  # noqa: ARG002
            return None

    def fake_session_local():  # noqa: ARG001
        return _Forwarder()

    monkeypatch.setattr(background_tailor, "SessionLocal", fake_session_local)


def _stub_claude(monkeypatch: pytest.MonkeyPatch, payloads: list[dict]) -> None:
    """Replace _build_claude with one that returns a Claude with our
    staged response sequence."""
    from app.ai.claude import ClaudeClient

    def fake_build():
        client = ClaudeClient(api_key="sk-test")
        # Replace the underlying messages.create with our staged fake
        client._client.messages = SimpleNamespace(create=_staged_create(payloads))  # type: ignore[attr-defined]
        return client

    monkeypatch.setattr(background_tailor, "_build_claude", fake_build)


@pytest.mark.asyncio
async def test_background_tailor_creates_all_three_artifact_kinds(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Happy path: profile + resume + Claude → resume + cover_letter +
    custom_answers all land in the DB."""
    profile = Profile(name="Test User", target_seniority="senior")
    resume = Resume(
        version=1,
        is_master=True,
        parsed_json={
            "name": "Test User",
            "experience": [
                {"company": "Acme", "title": "Engineer", "bullets": ["x"]}
            ],
            "education": [{"institution": "BITS", "degree": "B.E."}],
            "skills": ["Python"],
        },
    )
    job = Job(
        title="Senior Python Engineer",
        company="Razorpay",
        company_canonical="razorpay",
        description_md="Build payment infrastructure.",
    )
    db_session.add_all([profile, resume, job])
    await db_session.commit()

    # 10 Claude calls in order:
    #   1. extract_knockouts (called by generate_brief internally)
    #   2. tailoring brief
    #   3. tailoring execute (resume rewrite)
    #   4. cover-letter brief
    #   5. cover-letter execute
    #   6-10. 5 custom-question prompts
    _stub_session_local(monkeypatch, db_session)
    _stub_claude(
        monkeypatch,
        [
            _FAKE_KNOCKOUTS,
            _FAKE_BRIEF,
            _FAKE_REWRITTEN,
            _FAKE_COVER_BRIEF,
            _FAKE_COVER_LETTER,
            _FAKE_CQ,
            _FAKE_CQ,
            _FAKE_CQ,
            _FAKE_CQ,
            _FAKE_CQ,
        ],
    )

    await background_tailor.tailor_job_in_background(job.id)

    artifacts = (
        await db_session.execute(select(TailoredArtifact).where(TailoredArtifact.job_id == job.id))
    ).scalars().all()
    kinds = {a.kind for a in artifacts}
    assert kinds == {"resume", "cover_letter", "custom_answers"}

    # The custom_answers artifact should have all 5 keys
    cq = next(a for a in artifacts if a.kind == "custom_answers")
    assert cq.content_json is not None
    assert len(cq.content_json["answers"]) == 5

    # Two TailoringBrief rows: one for resume, one for cover_letter
    briefs = (
        await db_session.execute(select(TailoringBrief).where(TailoringBrief.job_id == job.id))
    ).scalars().all()
    brief_kinds = {b.kind for b in briefs}
    assert brief_kinds == {"resume", "cover_letter"}


@pytest.mark.asyncio
async def test_background_tailor_logs_and_returns_when_no_anthropic_key(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No Claude key → no panic, no artifacts, just a log line and a
    clean return."""
    profile = Profile(name="U")
    resume = Resume(version=1, is_master=True, parsed_json={"name": "U"})
    job = Job(title="t", company="c", company_canonical="c")
    db_session.add_all([profile, resume, job])
    await db_session.commit()

    _stub_session_local(monkeypatch, db_session)
    monkeypatch.setattr(background_tailor, "_build_claude", lambda: None)

    await background_tailor.tailor_job_in_background(job.id)

    artifacts = (
        await db_session.execute(select(TailoredArtifact))
    ).scalars().all()
    assert artifacts == []


@pytest.mark.asyncio
async def test_background_tailor_no_op_when_job_missing(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Job ID doesn't exist → log and return. (Race condition: user
    deletes Job between save and background task firing.)"""
    _stub_session_local(monkeypatch, db_session)
    # Should never even reach _build_claude; assert that.
    monkeypatch.setattr(
        background_tailor,
        "_build_claude",
        lambda: pytest.fail("should not have built Claude"),
    )
    await background_tailor.tailor_job_in_background(99999)
