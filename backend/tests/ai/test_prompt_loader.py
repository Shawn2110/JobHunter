from __future__ import annotations

from pathlib import Path

import pytest

from app.ai.prompt_loader import PromptError, PromptLoader
from app.ai.types import PromptKind, PromptManifest

REPO_ROOT = Path(__file__).resolve().parents[3]
PROMPTS_DIR = REPO_ROOT / "prompts"


@pytest.fixture
def loader() -> PromptLoader:
    return PromptLoader(prompts_dir=PROMPTS_DIR)


# ─── load() ──────────────────────────────────────────────────────────────────


def test_load_echo_parses_frontmatter(loader: PromptLoader) -> None:
    loaded = loader.load("static", "echo")
    assert loaded.manifest.name == "echo"
    assert loaded.manifest.kind == PromptKind.STATIC
    assert loaded.manifest.version >= 1
    assert loaded.manifest.model.startswith("claude-")
    assert loaded.manifest.output_schema == "string"
    assert "{{ message }}" in loaded.template


def test_load_unknown_prompt_raises(loader: PromptLoader) -> None:
    with pytest.raises(PromptError, match="not found"):
        loader.load("static", "definitely_not_a_real_prompt")


def test_load_with_enum_kind(loader: PromptLoader) -> None:
    loaded = loader.load(PromptKind.STATIC, "echo")
    assert loaded.manifest.name == "echo"


# ─── render() ────────────────────────────────────────────────────────────────


def test_render_substitutes_string(loader: PromptLoader) -> None:
    rendered = loader.render("static", "echo", {"message": "hello world"})
    assert "{{ message }}" not in rendered.body
    assert "hello world" in rendered.body
    assert rendered.manifest.name == "echo"


def test_render_missing_required_input_raises(loader: PromptLoader) -> None:
    with pytest.raises(PromptError, match="missing required inputs"):
        loader.render("static", "echo", {})


def test_render_unexpected_input_raises(loader: PromptLoader) -> None:
    with pytest.raises(PromptError, match="unexpected inputs"):
        loader.render("static", "echo", {"message": "hi", "extra": "no"})


# ─── validate_response() ─────────────────────────────────────────────────────


def test_validate_response_string_accepts_string(loader: PromptLoader) -> None:
    loaded = loader.load("static", "echo")
    loader.validate_response(loaded.manifest, "anything")


def test_validate_response_string_rejects_non_string(loader: PromptLoader) -> None:
    loaded = loader.load("static", "echo")
    with pytest.raises(PromptError, match="output_schema is 'string'"):
        loader.validate_response(loaded.manifest, {"not": "a string"})


def test_validate_response_json_schema_accepts_match() -> None:
    manifest = PromptManifest(
        name="dummy",
        kind=PromptKind.STATIC,
        version=1,
        inputs=[],
        output_schema={
            "type": "object",
            "properties": {"verdict": {"type": "string"}},
            "required": ["verdict"],
        },
        model="claude-sonnet-4-6",
    )
    PromptLoader(PROMPTS_DIR).validate_response(manifest, {"verdict": "strong"})


def test_validate_response_json_schema_rejects_mismatch() -> None:
    manifest = PromptManifest(
        name="dummy",
        kind=PromptKind.STATIC,
        version=1,
        inputs=[],
        output_schema={
            "type": "object",
            "properties": {"verdict": {"type": "string"}},
            "required": ["verdict"],
        },
        model="claude-sonnet-4-6",
    )
    with pytest.raises(PromptError, match="JSON Schema validation"):
        PromptLoader(PROMPTS_DIR).validate_response(manifest, {"missing": "field"})
