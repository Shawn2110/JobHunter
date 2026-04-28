from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.ai.claude import ClaudeClient
from app.ai.knockouts import extract_knockouts
from app.ai.prompt_loader import PromptLoader

REPO_ROOT = Path(__file__).resolve().parents[3]
PROMPTS_DIR = REPO_ROOT / "prompts"


@pytest.mark.asyncio
async def test_extract_knockouts_parses_response(
    frozen_claude: ClaudeClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        frozen_claude._fake_messages.response.content[0],  # type: ignore[attr-defined]
        "text",
        json.dumps({
            "knockouts": [
                {
                    "question_text": "Are you authorized to work in the US?",
                    "type": "yes_no",
                    "criterion": "us_work_auth",
                    "required": True,
                },
                {
                    "question_text": "Do you have at least 5 years of Python experience?",
                    "type": "years",
                    "criterion": "min_5_years_python",
                    "required": True,
                },
            ]
        }),
    )

    loader = PromptLoader(PROMPTS_DIR)
    result = await extract_knockouts(
        "Senior Python Engineer",
        "5+ years Python required. US work auth required.",
        claude=frozen_claude,
        loader=loader,
    )
    assert len(result) == 2
    assert result[0]["criterion"] == "us_work_auth"


@pytest.mark.asyncio
async def test_extract_knockouts_empty_description_returns_empty(
    frozen_claude: ClaudeClient,
) -> None:
    loader = PromptLoader(PROMPTS_DIR)
    result = await extract_knockouts(
        "x", "", claude=frozen_claude, loader=loader
    )
    assert result == []
    # No call was made to Claude
    assert frozen_claude._fake_messages.calls == []  # type: ignore[attr-defined]
