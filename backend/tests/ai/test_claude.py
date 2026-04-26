from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.ai.claude import ClaudeClient, ClaudeResult, estimate_cost_usd
from app.ai.prompt_loader import PromptError, PromptLoader

REPO_ROOT = Path(__file__).resolve().parents[3]
PROMPTS_DIR = REPO_ROOT / "prompts"


# ─── complete() with raw string prompt ──────────────────────────────────────


@pytest.mark.asyncio
async def test_complete_returns_text_and_token_counts(
    frozen_claude: ClaudeClient,
) -> None:
    result = await frozen_claude.complete("hello")
    assert isinstance(result, ClaudeResult)
    assert result.text == "FROZEN_RESPONSE"
    assert result.input_tokens == 10
    assert result.output_tokens == 20
    assert result.duration_ms >= 0
    assert result.cost_usd is not None and result.cost_usd > 0


@pytest.mark.asyncio
async def test_complete_uses_default_model_for_string_prompt(
    frozen_claude: ClaudeClient,
) -> None:
    await frozen_claude.complete("hi")
    sent = frozen_claude._fake_messages.calls[-1]  # type: ignore[attr-defined]
    assert sent["model"] == frozen_claude.default_model
    assert sent["messages"][0]["content"] == "hi"


@pytest.mark.asyncio
async def test_complete_explicit_model_overrides_default(
    frozen_claude: ClaudeClient,
) -> None:
    await frozen_claude.complete("hi", model="claude-opus-4-7")
    sent = frozen_claude._fake_messages.calls[-1]  # type: ignore[attr-defined]
    assert sent["model"] == "claude-opus-4-7"


# ─── complete() with RenderedPrompt ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_complete_with_rendered_prompt_uses_manifest_defaults(
    frozen_claude: ClaudeClient,
) -> None:
    loader = PromptLoader(PROMPTS_DIR)
    rendered = loader.render("static", "echo", {"message": "ping"})
    result = await frozen_claude.complete(rendered)

    sent = frozen_claude._fake_messages.calls[-1]  # type: ignore[attr-defined]
    assert sent["model"] == rendered.manifest.model
    assert sent["max_tokens"] == rendered.manifest.max_tokens
    assert sent["temperature"] == rendered.manifest.temperature
    assert sent["messages"][0]["content"] == rendered.body
    assert result.model == rendered.manifest.model


# ─── complete_json() ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_complete_json_parses_response(
    frozen_claude: ClaudeClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Override the frozen response with valid JSON for this test only.
    monkeypatch.setattr(
        frozen_claude._fake_messages.response.content[0],  # type: ignore[attr-defined]
        "text",
        json.dumps({"verdict": "strong", "score": 9}),
    )
    parsed, result = await frozen_claude.complete_json("any prompt")
    assert parsed == {"verdict": "strong", "score": 9}
    assert isinstance(result, ClaudeResult)


@pytest.mark.asyncio
async def test_complete_json_strips_code_fences(
    frozen_claude: ClaudeClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fenced = "```json\n" + json.dumps({"ok": True}) + "\n```"
    monkeypatch.setattr(
        frozen_claude._fake_messages.response.content[0],  # type: ignore[attr-defined]
        "text",
        fenced,
    )
    parsed, _ = await frozen_claude.complete_json("any prompt")
    assert parsed == {"ok": True}


@pytest.mark.asyncio
async def test_complete_json_raises_on_non_json(
    frozen_claude: ClaudeClient,
) -> None:
    with pytest.raises(PromptError, match="non-JSON"):
        await frozen_claude.complete_json("any prompt")  # FROZEN_RESPONSE is not JSON


# ─── cost estimator ─────────────────────────────────────────────────────────


def test_estimate_cost_known_model() -> None:
    cost = estimate_cost_usd("claude-sonnet-4-6", 1_000_000, 1_000_000)
    assert cost == pytest.approx(3.0 + 15.0, rel=1e-6)


def test_estimate_cost_unknown_model_returns_none() -> None:
    assert estimate_cost_usd("claude-something-future", 100, 100) is None
