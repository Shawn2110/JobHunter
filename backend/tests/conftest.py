from __future__ import annotations

from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.ai.claude import ClaudeClient
from app.db import Base
from app.main import app
import app.models  # noqa: F401  — register all models on Base.metadata


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    """Per-test in-memory SQLite session.

    Creates all tables fresh, yields one session, drops everything on
    teardown. Tests that need persistence across calls within one
    test should use this single session for all reads and writes.
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sessionmaker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with sessionmaker() as session:
        yield session
    await engine.dispose()


@pytest.fixture
async def client() -> AsyncClient:
    """Async HTTP client wired to the FastAPI app over ASGITransport.

    No real network calls; this lets every test hit the app in-process.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
async def api_client(
    db_session: AsyncSession,
    frozen_claude: ClaudeClient,
) -> AsyncIterator[AsyncClient]:
    """ASGI client with get_session and get_claude dependencies overridden.

    Routes that touch the DB use the in-memory db_session; routes that
    call Claude use the frozen fake. Cleans up dependency_overrides on
    teardown so tests don't leak state into each other.
    """
    from app.db import get_session
    from app.deps import get_claude

    async def _get_session_override() -> AsyncIterator[AsyncSession]:
        yield db_session

    def _get_claude_override() -> ClaudeClient:
        return frozen_claude

    app.dependency_overrides[get_session] = _get_session_override
    app.dependency_overrides[get_claude] = _get_claude_override
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c
    finally:
        app.dependency_overrides.clear()


class _FakeMessages:
    """Stand-in for `AsyncAnthropic.messages` used by frozen_claude.

    Records every `create()` call so tests can assert on the args (model,
    messages, temperature, etc.) without hitting the real API.
    """

    def __init__(self, response: SimpleNamespace) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> SimpleNamespace:
        self.calls.append(kwargs)
        return self.response


@pytest.fixture
def frozen_claude(monkeypatch: pytest.MonkeyPatch) -> ClaudeClient:
    """ClaudeClient whose underlying SDK is replaced with a deterministic fake.

    Every call returns the same `FROZEN_RESPONSE` text and the same
    (10 input / 20 output) token counts, regardless of input. The
    underlying `_FakeMessages` records every call so tests can assert
    on the parameters that were sent. Use this for any AI-using
    service test — the real Anthropic API is never reached.

    Per docs/Agent.md § Testing: "Tests for AI-using services should use
    frozen fixture responses... Never hit the live Claude API in CI."
    """
    response = SimpleNamespace(
        content=[SimpleNamespace(text="FROZEN_RESPONSE")],
        usage=SimpleNamespace(input_tokens=10, output_tokens=20),
        model="claude-sonnet-4-6",
        id="msg_frozen",
        role="assistant",
        stop_reason="end_turn",
    )
    fake_messages = _FakeMessages(response)

    client = ClaudeClient(api_key="sk-test-fake")
    monkeypatch.setattr(client._client, "messages", fake_messages)
    # Expose the recorder for assertions.
    client._fake_messages = fake_messages  # type: ignore[attr-defined]
    return client
