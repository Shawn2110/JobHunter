from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.trust.longitudinal import (
    canonical_job_id,
    evaluate_longitudinal,
    record_sighting,
)


def test_canonical_job_id_stable_under_company_suffixes() -> None:
    a = canonical_job_id("Razorpay Pvt Ltd", "Senior Engineer", "build payments")
    b = canonical_job_id("Razorpay", "Senior Engineer", "build payments")
    assert a == b


def test_canonical_job_id_different_for_different_titles() -> None:
    a = canonical_job_id("Acme", "Senior Engineer", "x")
    b = canonical_job_id("Acme", "Junior Engineer", "x")
    assert a != b


@pytest.mark.asyncio
async def test_first_sighting_returns_no_signals(db_session: AsyncSession) -> None:
    await record_sighting(
        company="Acme",
        title="Engineer",
        description="x",
        source_url="https://acme.com/1",
        session=db_session,
    )
    signals, score = await evaluate_longitudinal(
        company="Acme",
        title="Engineer",
        description="x",
        session=db_session,
    )
    assert signals == []
    assert score is None


@pytest.mark.asyncio
async def test_three_reposts_in_60_days_triggers_warning(
    db_session: AsyncSession,
) -> None:
    now = datetime.now(timezone.utc)
    for i in range(4):
        row = await record_sighting(
            company="Acme",
            title="Engineer",
            description="build stuff",
            source_url=f"https://acme.com/{i}",
            session=db_session,
        )
        # Backdate so all sit within 60 days
        row.seen_at = now - timedelta(days=10 * i)
        await db_session.commit()

    signals, score = await evaluate_longitudinal(
        company="Acme",
        title="Engineer",
        description="build stuff",
        session=db_session,
        now=now,
    )
    kinds = [s.kind for s in signals]
    assert "reposts" in kinds
    assert score is not None and score < 100


@pytest.mark.asyncio
async def test_six_reposts_in_90_days_triggers_strong(
    db_session: AsyncSession,
) -> None:
    now = datetime.now(timezone.utc)
    for i in range(7):
        row = await record_sighting(
            company="Acme",
            title="Engineer",
            description="build stuff",
            source_url=f"https://acme.com/{i}",
            session=db_session,
        )
        row.seen_at = now - timedelta(days=12 * i)  # all within 90d
        await db_session.commit()

    signals, score = await evaluate_longitudinal(
        company="Acme",
        title="Engineer",
        description="build stuff",
        session=db_session,
        now=now,
    )
    severities = [s.severity for s in signals]
    assert "strong" in severities
    assert score is not None and score < 70
