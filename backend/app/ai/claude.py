from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any

import structlog
from anthropic import AsyncAnthropic
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.prompt_loader import PromptError, PromptLoader
from app.ai.types import RenderedPrompt
from app.models import AiCall

log = structlog.get_logger("app.ai.claude")


# Update from https://www.anthropic.com/pricing — small reference table the
# user can edit. Returns None for unknown models so logging never blocks.
PRICES_USD_PER_M_TOKENS: dict[str, dict[str, float]] = {
    "claude-sonnet-4-6": {"input": 3.00, "output": 15.00},
    "claude-opus-4-7": {"input": 15.00, "output": 75.00},
    "claude-haiku-4-5-20251001": {"input": 1.00, "output": 5.00},
}


def estimate_cost_usd(
    model: str, input_tokens: int, output_tokens: int
) -> float | None:
    rates = PRICES_USD_PER_M_TOKENS.get(model)
    if rates is None:
        return None
    return (
        input_tokens * rates["input"] / 1_000_000
        + output_tokens * rates["output"] / 1_000_000
    )


@dataclass(frozen=True)
class ClaudeResult:
    text: str
    input_tokens: int
    output_tokens: int
    cost_usd: float | None
    duration_ms: int
    model: str


class ClaudeClient:
    """Async wrapper around the Anthropic SDK.

    Responsibilities:
    - Model selection: pass a `RenderedPrompt` and the manifest's model
      is used; pass a raw string and `default_model` is used.
    - Retry-on-5xx via the SDK's `max_retries`.
    - Token-cost logging: when an `AsyncSession` is provided, every call
      writes a row to the `ai_call` table.
    - JSON helper: `complete_json` parses the response and (optionally)
      validates it against a JSON Schema declared on the prompt manifest.
    """

    def __init__(
        self,
        api_key: str,
        default_model: str = "claude-sonnet-4-6",
        high_stakes_model: str = "claude-opus-4-7",
        max_retries: int = 1,
    ) -> None:
        self._client = AsyncAnthropic(api_key=api_key, max_retries=max_retries)
        self.default_model = default_model
        self.high_stakes_model = high_stakes_model

    async def complete(
        self,
        prompt: str | RenderedPrompt,
        *,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        system: str | None = None,
        session: AsyncSession | None = None,
    ) -> ClaudeResult:
        cfg = _resolve(prompt, model, max_tokens, temperature, self.default_model)

        kwargs: dict[str, Any] = {
            "model": cfg["model"],
            "max_tokens": cfg["max_tokens"],
            "temperature": cfg["temperature"],
            "messages": [{"role": "user", "content": cfg["prompt_text"]}],
        }
        if system is not None:
            kwargs["system"] = system

        started = time.perf_counter()
        try:
            message = await self._client.messages.create(**kwargs)
        except Exception as e:
            duration_ms = int((time.perf_counter() - started) * 1000)
            await self._maybe_log(
                session,
                model=cfg["model"],
                prompt_kind=cfg["prompt_kind"],
                prompt_name=cfg["prompt_name"],
                prompt_version=cfg["prompt_version"],
                input_tokens=0,
                output_tokens=0,
                cost_usd=None,
                duration_ms=duration_ms,
                succeeded=False,
                error_message=repr(e)[:1000],
            )
            log.error(
                "claude.error",
                model=cfg["model"],
                prompt_name=cfg["prompt_name"],
                error=type(e).__name__,
            )
            raise

        duration_ms = int((time.perf_counter() - started) * 1000)

        text = "".join(
            getattr(block, "text", "") for block in message.content
        )
        input_tokens = message.usage.input_tokens
        output_tokens = message.usage.output_tokens
        cost = estimate_cost_usd(cfg["model"], input_tokens, output_tokens)

        await self._maybe_log(
            session,
            model=cfg["model"],
            prompt_kind=cfg["prompt_kind"],
            prompt_name=cfg["prompt_name"],
            prompt_version=cfg["prompt_version"],
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
            duration_ms=duration_ms,
            succeeded=True,
            error_message=None,
        )

        log.info(
            "claude.complete",
            model=cfg["model"],
            prompt_name=cfg["prompt_name"],
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
            duration_ms=duration_ms,
        )

        return ClaudeResult(
            text=text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
            duration_ms=duration_ms,
            model=cfg["model"],
        )

    async def complete_json(
        self,
        prompt: str | RenderedPrompt,
        *,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        system: str | None = None,
        loader: PromptLoader | None = None,
        session: AsyncSession | None = None,
    ) -> tuple[dict[str, Any], ClaudeResult]:
        """Send a completion expected to return JSON.

        If `prompt` is a RenderedPrompt and a `loader` is provided, the
        parsed response is validated against the manifest's
        `output_schema`.
        """
        result = await self.complete(
            prompt,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
            session=session,
        )

        try:
            parsed = json.loads(_strip_code_fences(result.text))
        except json.JSONDecodeError as e:
            raise PromptError(
                f"complete_json: model returned non-JSON: {e.msg} "
                f"(text starts: {result.text[:120]!r})"
            ) from e

        if isinstance(prompt, RenderedPrompt) and loader is not None:
            loader.validate_response(prompt.manifest, parsed)

        return parsed, result

    @staticmethod
    async def _maybe_log(session: AsyncSession | None, **fields: Any) -> None:
        if session is None:
            return
        session.add(AiCall(**fields))
        await session.commit()


def _resolve(
    prompt: str | RenderedPrompt,
    model_override: str | None,
    max_tokens_override: int | None,
    temperature_override: float | None,
    fallback_model: str,
) -> dict[str, Any]:
    """Pick model, max_tokens, temperature; carry prompt-name metadata."""
    if isinstance(prompt, RenderedPrompt):
        manifest = prompt.manifest
        return {
            "prompt_text": prompt.body,
            "model": model_override or manifest.model,
            "max_tokens": (
                max_tokens_override
                if max_tokens_override is not None
                else manifest.max_tokens
            ),
            "temperature": (
                temperature_override
                if temperature_override is not None
                else manifest.temperature
            ),
            "prompt_kind": manifest.kind.value,
            "prompt_name": manifest.name,
            "prompt_version": manifest.version,
        }
    return {
        "prompt_text": prompt,
        "model": model_override or fallback_model,
        "max_tokens": max_tokens_override or 4096,
        "temperature": temperature_override if temperature_override is not None else 0.2,
        "prompt_kind": None,
        "prompt_name": None,
        "prompt_version": None,
    }


def _strip_code_fences(text: str) -> str:
    """Strip ```json ... ``` fences if Claude wrapped the response in them."""
    s = text.strip()
    if s.startswith("```"):
        # Drop the opening fence (with optional language tag) and trailing fence.
        s = s.split("\n", 1)[1] if "\n" in s else ""
        if s.endswith("```"):
            s = s[: -len("```")].rstrip()
    return s
