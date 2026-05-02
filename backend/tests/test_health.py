from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_returns_ok(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_providers_endpoint_shape(client: AsyncClient) -> None:
    response = await client.get("/providers")
    assert response.status_code == 200
    body = response.json()
    # Shape only — values depend on which keys are set in .env
    assert "ai_configured" in body
    assert "search_provider" in body
    assert "crawler" in body
    assert "github_token_configured" in body
