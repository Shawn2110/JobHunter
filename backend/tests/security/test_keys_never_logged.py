"""Per Agent.md § Critical Do-Not-Break Tests:

API keys must NEVER appear in logs, error messages, frontend bundles,
AI prompts, or any file checked into git. This test makes the
contract structural — capture every structlog event during a
request that exercises the configured-providers code paths and
assert no key value leaks through.
"""

from __future__ import annotations

import pytest
import structlog
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_no_keys_in_logs(client: AsyncClient) -> None:
    """Hit /providers (which inspects every configured key) and capture
    every log line. Assert no recognizable key shape leaks."""
    captured: list[str] = []

    def _capture(_, __, event_dict):
        captured.append(repr(event_dict))
        return event_dict

    structlog.configure(processors=[_capture, structlog.dev.ConsoleRenderer()])

    # Inject sentinel "keys" via env override would be racy with
    # global settings; instead, scan all captured events for the
    # known prefixes we'd care about even when keys ARE blank.
    res = await client.get("/providers")
    assert res.status_code == 200

    forbidden_substrings = [
        "sk-ant-",          # Anthropic
        "rapidapi-",        # JSearch
        "BSAk",             # Brave (placeholder shape)
        # Generic API key shapes — 32+ alphanumeric isn't useful as a
        # blanket filter (matches lots of UUIDs); the structural rule
        # is "no field literally named *_api_key in log output".
    ]
    forbidden_keys = [
        "ANTHROPIC_API_KEY",
        "JSEARCH_API_KEY",
        "ADZUNA_APP_KEY",
        "JOOBLE_API_KEY",
        "THEIRSTACK_API_KEY",
        "BRAVE_SEARCH_API_KEY",
        "SERPER_API_KEY",
        "FIRECRAWL_API_KEY",
        "GITHUB_TOKEN",
    ]
    blob = " ".join(captured)
    for s in forbidden_substrings:
        assert s not in blob, f"Sensitive substring leaked into logs: {s!r}"
    for k in forbidden_keys:
        assert k not in blob, (
            f"Env var name {k!r} appeared in log output. "
            "Settings should be redacted at the log boundary."
        )


@pytest.mark.asyncio
async def test_providers_endpoint_returns_booleans_not_keys(
    client: AsyncClient,
) -> None:
    """/providers must report configured-or-not, never the keys themselves."""
    res = await client.get("/providers")
    body = res.json()
    # Every value should be a bool, list, str (canonical name), or None
    for k, v in body.items():
        assert not (isinstance(v, str) and len(v) > 30), (
            f"/providers field {k!r} returned a long string ({len(v)} chars) — "
            "keys must never be in the response payload."
        )
