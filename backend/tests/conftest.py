from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from app.ai.claude import ClaudeClient
from app.main import app


@pytest.fixture
async def client() -> AsyncClient:
    """Async HTTP client wired to the FastAPI app over ASGITransport.

    No real network calls; this lets every test hit the app in-process.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


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
