from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from fastapi import HTTPException, status

from app.ai.claude import ClaudeClient
from app.ai.prompt_loader import PromptLoader
from app.config import REPO_ROOT, settings


@lru_cache(maxsize=1)
def get_prompt_loader() -> PromptLoader:
    """Singleton PromptLoader rooted at <repo_root>/prompts."""
    return PromptLoader(prompts_dir=REPO_ROOT / "prompts")


@lru_cache(maxsize=1)
def _get_claude_client() -> ClaudeClient:
    if not settings.anthropic_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "ANTHROPIC_API_KEY is not configured. Set it in .env to enable "
                "AI features."
            ),
        )
    return ClaudeClient(
        api_key=settings.anthropic_api_key,
        default_model=settings.anthropic_model_default,
        high_stakes_model=settings.anthropic_model_high_stakes,
    )


def get_claude() -> ClaudeClient:
    """FastAPI dependency. Raises 503 if AI is not configured."""
    return _get_claude_client()


def resume_storage_dir() -> Path:
    """Where uploaded resumes are persisted on disk."""
    p = REPO_ROOT / "data" / "resumes"
    p.mkdir(parents=True, exist_ok=True)
    return p
