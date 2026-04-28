from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.discovery.adapters.base import DiscoveryAdapter
from app.discovery.types import DiscoveredJob, SearchInput
from app.models import Job, SearchQuery
from app.services.diff import run_saved_search


class _StaticAdapter(DiscoveryAdapter):
    def __init__(self, jobs: list[DiscoveredJob]) -> None:
        self.name = "static"
        self.source_kind = "aggregator"
        self._jobs = jobs

    def is_configured(self) -> bool:
        return True

    async def _fetch(self, query: SearchInput) -> list[DiscoveredJob]:
        return self._jobs


def _seed_dj(title: str, company: str) -> DiscoveredJob:
    return DiscoveredJob(
        title=title,
        company=company,
        apply_url=f"https://example.com/{company}/{title}",
        description_md=f"Build {title} systems",
        source_provider="static",
    )


@pytest.mark.asyncio
async def test_run_saved_search_first_run_returns_all_as_new(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sq = SearchQuery(
        name="test",
        role="engineer",
        locations_json=["Bengaluru"],
        modes_enabled_json=["aggregator"],
    )
    db_session.add(sq)
    await db_session.commit()

    # Seed two existing jobs already in the DB BEFORE first run
    db_session.add_all([
        Job(title="Existing", company="Old", company_canonical="old"),
    ])
    await db_session.commit()

    # Patch the orchestrator's default adapters
    from app.discovery import orchestrator
    monkeypatch.setattr(
        orchestrator,
        "default_aggregator_adapters",
        lambda: [_StaticAdapter([_seed_dj("New Engineer", "Acme")])],
    )

    result = await run_saved_search(sq, db_session)
    assert result.previous_run_at is None
    # First run: all jobs in DB count as new (no baseline)
    assert len(result.new_jobs) >= 1
    # last_run_at was set
    assert sq.last_run_at is not None


@pytest.mark.asyncio
async def test_run_saved_search_second_run_only_returns_new(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sq = SearchQuery(
        name="t",
        role="engineer",
        modes_enabled_json=["aggregator"],
    )
    db_session.add(sq)
    await db_session.commit()

    from app.discovery import orchestrator

    # First run discovers one job
    monkeypatch.setattr(
        orchestrator,
        "default_aggregator_adapters",
        lambda: [_StaticAdapter([_seed_dj("Engineer A", "Acme")])],
    )
    first = await run_saved_search(sq, db_session)
    assert first.previous_run_at is None

    # Manually push the existing job's first_seen_at into the past so
    # the diff window has a clean before/after divide.
    existing_a = first.new_jobs[0]
    old_seen = datetime.now(timezone.utc) - timedelta(hours=1)
    existing_a.first_seen_at = old_seen
    existing_a.last_seen_at = old_seen
    sq.last_run_at = datetime.now(timezone.utc) - timedelta(seconds=30)
    await db_session.commit()
    old_run = sq.last_run_at

    # Second run discovers a NEW job + the existing one
    monkeypatch.setattr(
        orchestrator,
        "default_aggregator_adapters",
        lambda: [
            _StaticAdapter([
                _seed_dj("Engineer A", "Acme"),
                _seed_dj("Engineer B", "Beta"),
            ])
        ],
    )
    second = await run_saved_search(sq, db_session)
    assert second.previous_run_at == old_run
    new_titles = {j.title for j in second.new_jobs}
    assert "Engineer B" in new_titles
    assert "Engineer A" not in new_titles  # already existed before old_run
