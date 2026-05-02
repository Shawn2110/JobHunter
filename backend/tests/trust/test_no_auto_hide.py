"""Per Agent.md § Critical Do-Not-Break Tests:

The trust subsystem is informational, never gatekeeping. The feed
returned by /search must surface every job — flagged or not. This test
guards that contract.
"""

from __future__ import annotations

import json

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.discovery import orchestrator
from app.discovery.adapters.base import DiscoveryAdapter
from app.discovery.types import DiscoveredJob, SearchInput
from app.models import Job, TrustAssessment


class _StaticAdapter(DiscoveryAdapter):
    def __init__(self, jobs: list[DiscoveredJob]) -> None:
        self.name = "static"
        self.source_kind = "aggregator"
        self._jobs = jobs

    def is_configured(self) -> bool:
        return True

    async def _fetch(self, query: SearchInput) -> list[DiscoveredJob]:
        return self._jobs


@pytest.mark.asyncio
async def test_search_response_includes_likely_scam_jobs(
    api_client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Even when a job's trust verdict is likely_scam, /search must
    return it. We never silently filter the feed.
    """
    monkeypatch.setattr(
        orchestrator,
        "default_keyless_adapters",
        lambda: [
            _StaticAdapter([
                DiscoveredJob(
                    title="Engineer",
                    company="Acme",
                    apply_url="https://acme.com/1",
                    description_md="Build things",
                    source_provider="static",
                ),
                DiscoveredJob(
                    title="Engineer",
                    company="Sketchy",
                    apply_url="https://sketchy.com/1",
                    description_md="Pay registration fee to apply",
                    source_provider="static",
                ),
            ])
        ],
    )

    res = await api_client.post("/search", json={"role": "engineer"})
    assert res.status_code == 200
    body = res.json()
    titles = {(j["title"], j["company"]) for j in body["jobs"]}
    assert ("Engineer", "Acme") in titles
    assert ("Engineer", "Sketchy") in titles


@pytest.mark.asyncio
async def test_listing_includes_jobs_with_likely_scam_verdicts(
    api_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """GET /jobs must include rows that carry a likely_scam verdict —
    no auto-hiding at the listing layer either.
    """
    sketchy = Job(
        title="Engineer",
        company="Sketchy",
        company_canonical="sketchy",
        description_md="Pay $$$ to apply",
    )
    db_session.add(sketchy)
    await db_session.commit()

    db_session.add(
        TrustAssessment(
            job_id=sketchy.id,
            verdict="likely_scam",
            scam_signals_json=[{"id": "x", "severity": "scam_strong", "description": "y"}],
            ghost_job_signals_json=[],
            positive_signals_json=[],
            rationale_md="Test fixture.",
            static_check_score=20,
            ai_check_score=10,
            longitudinal_score=None,
        )
    )
    await db_session.commit()

    res = await api_client.get("/jobs")
    assert res.status_code == 200
    body = res.json()
    assert any(
        j["company"] == "Sketchy"
        and j["trust_assessment"]
        and j["trust_assessment"]["verdict"] == "likely_scam"
        for j in body
    )
