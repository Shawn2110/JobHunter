from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_add_list_remove_watchlist(api_client: AsyncClient) -> None:
    res = await api_client.post(
        "/watchlist",
        json={"name": "Razorpay", "careers_url": "https://razorpay.com/jobs"},
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["name"] == "Razorpay"
    company_id = body["id"]

    listing = await api_client.get("/watchlist")
    assert listing.status_code == 200
    assert any(r["id"] == company_id for r in listing.json())

    delete = await api_client.delete(f"/watchlist/{company_id}")
    assert delete.status_code == 204

    after = await api_client.get("/watchlist")
    assert all(r["id"] != company_id for r in after.json())


@pytest.mark.asyncio
async def test_duplicate_url_rejected(api_client: AsyncClient) -> None:
    payload = {"name": "Acme", "careers_url": "https://acme.com/careers"}
    first = await api_client.post("/watchlist", json=payload)
    assert first.status_code == 201
    second = await api_client.post("/watchlist", json=payload)
    assert second.status_code == 409
