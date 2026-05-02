from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_export_returns_all_tables(api_client: AsyncClient) -> None:
    res = await api_client.get("/admin/export")
    assert res.status_code == 200
    body = res.json()
    assert "exported_at" in body
    # Spot-check that the expected table set is present
    expected = {
        "profile",
        "profile_handle",
        "resume",
        "job",
        "fit_assessment",
        "trust_assessment",
        "contact",
        "outreach_draft",
        "tailoring_brief",
        "tailored_artifact",
        "watchlist_company",
        "ai_call",
    }
    assert expected.issubset(set(body["tables"].keys()))


@pytest.mark.asyncio
async def test_wipe_requires_literal_confirmation(api_client: AsyncClient) -> None:
    bad = await api_client.post("/admin/wipe", json={"confirmation": "yes"})
    assert bad.status_code == 400


@pytest.mark.asyncio
async def test_wipe_with_correct_confirmation_succeeds(
    api_client: AsyncClient,
) -> None:
    # Add a row first so wipe has something to delete
    await api_client.post(
        "/watchlist", json={"name": "Acme", "careers_url": "https://acme.com/c"}
    )
    res = await api_client.post("/admin/wipe", json={"confirmation": "WIPE"})
    assert res.status_code == 200
    assert res.json()["deleted_rows"]["watchlist_company"] >= 1
    after = await api_client.get("/watchlist")
    assert after.json() == []
