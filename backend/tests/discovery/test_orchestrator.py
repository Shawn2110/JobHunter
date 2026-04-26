from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.discovery.adapters.base import DiscoveryAdapter
from app.discovery.orchestrator import run_discovery
from app.discovery.types import DiscoveredJob, SearchInput
from app.models import Job, JobSource


class _FakeAdapter(DiscoveryAdapter):
    """Returns a fixed list; reports configured=True."""

    def __init__(self, name: str, jobs: list[DiscoveredJob]) -> None:
        self.name = name
        self.source_kind = "aggregator"
        self._jobs = jobs

    def is_configured(self) -> bool:
        return True

    async def _fetch(self, query: SearchInput) -> list[DiscoveredJob]:
        return self._jobs


def _job(
    title: str,
    company: str,
    apply_url: str,
    description: str = "",
    source_provider: str = "fake",
) -> DiscoveredJob:
    return DiscoveredJob(
        title=title,
        company=company,
        apply_url=apply_url,
        description_md=description,
        posted_at=datetime.now(timezone.utc),
        source_provider=source_provider,
    )


@pytest.mark.asyncio
async def test_orchestrator_inserts_new_jobs(db_session: AsyncSession) -> None:
    adapter = _FakeAdapter(
        "alpha",
        [
            _job("Senior Engineer", "Acme", "https://acme.com/jobs/1", "build things"),
            _job("Junior Engineer", "Acme", "https://acme.com/jobs/2", "build other things"),
        ],
    )
    new_jobs, updated = await run_discovery(
        SearchInput(role="engineer"), session=db_session, adapters=[adapter]
    )
    assert len(new_jobs) == 2
    assert len(updated) == 0
    count = (await db_session.execute(select(func.count()).select_from(Job))).scalar_one()
    assert count == 2


@pytest.mark.asyncio
async def test_orchestrator_dedupes_within_batch(db_session: AsyncSession) -> None:
    a = _FakeAdapter(
        "alpha",
        [_job("Senior Engineer", "Acme", "https://a.com/1", "build stuff")],
    )
    b = _FakeAdapter(
        "beta",
        [_job("Senior Engineer", "Acme Inc", "https://b.com/1", "build stuff")],
    )
    new_jobs, updated = await run_discovery(
        SearchInput(role="engineer"), session=db_session, adapters=[a, b]
    )
    assert len(new_jobs) == 1
    job = new_jobs[0]
    sources = (
        await db_session.execute(select(JobSource).where(JobSource.job_id == job.id))
    ).scalars().all()
    providers = {s.source_provider for s in sources}
    assert providers == {"alpha", "beta"}


@pytest.mark.asyncio
async def test_orchestrator_dedupes_against_existing_db(
    db_session: AsyncSession,
) -> None:
    adapter = _FakeAdapter(
        "alpha",
        [_job("Senior Engineer", "Acme", "https://a.com/1", "build payment systems for businesses across India")],
    )
    # First run: insert
    new1, _ = await run_discovery(
        SearchInput(role="engineer"), session=db_session, adapters=[adapter]
    )
    assert len(new1) == 1

    # Second run with same job (slightly different description) → no new row
    adapter2 = _FakeAdapter(
        "beta",
        [_job("Senior Engineer", "Acme Inc.", "https://b.com/1", "build payment systems for businesses across India.")],
    )
    new2, updated2 = await run_discovery(
        SearchInput(role="engineer"), session=db_session, adapters=[adapter2]
    )
    assert len(new2) == 0
    assert len(updated2) == 1

    # Original job now has two sources
    job = updated2[0]
    sources = (
        await db_session.execute(select(JobSource).where(JobSource.job_id == job.id))
    ).scalars().all()
    providers = {s.source_provider for s in sources}
    assert providers == {"alpha", "beta"}


@pytest.mark.asyncio
async def test_orchestrator_returns_empty_when_no_adapters_configured(
    db_session: AsyncSession,
) -> None:
    class _Off(DiscoveryAdapter):
        name = "off"

        def is_configured(self) -> bool:
            return False

        async def _fetch(self, query: SearchInput) -> list[DiscoveredJob]:
            raise RuntimeError("should not be called")

    new, upd = await run_discovery(
        SearchInput(role="x"), session=db_session, adapters=[_Off()]
    )
    assert new == [] and upd == []
