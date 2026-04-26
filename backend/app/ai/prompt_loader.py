from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator
from jsonschema import ValidationError as JsonSchemaError
from pydantic import ValidationError as PydanticError

from app.ai.types import LoadedPrompt, PromptKind, PromptManifest, RenderedPrompt


class PromptError(Exception):
    """Raised for any loader, render, or response-validation failure."""


_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)
_PLACEHOLDER_RE = re.compile(r"{{\s*(\w+)\s*}}")


class PromptLoader:
    """Loads versioned `.md` prompts with YAML frontmatter.

    Hot-reloads on every call (no caching) so users can edit a prompt
    file and see the effect on the next request without restarting the
    backend. Validates frontmatter against PromptManifest, validates
    inputs against the manifest's declared input set, and validates
    AI responses against `output_schema` when it's a JSON Schema.

    Template substitution is intentionally limited to `{{ var_name }}`
    placeholders — a strict subset of Jinja2. Promote to real Jinja2
    only when a prompt genuinely needs conditionals or loops.
    """

    def __init__(self, prompts_dir: Path | str) -> None:
        self.prompts_dir = Path(prompts_dir)

    def load(self, kind: PromptKind | str, name: str) -> LoadedPrompt:
        kind = PromptKind(kind) if isinstance(kind, str) else kind
        path = self.prompts_dir / kind.value / f"{name}.md"
        if not path.exists():
            raise PromptError(f"Prompt not found: {path}")

        raw = path.read_text(encoding="utf-8")
        match = _FRONTMATTER_RE.match(raw)
        if not match:
            raise PromptError(
                f"{path}: missing YAML frontmatter delimited by --- on lines 1 and N"
            )

        try:
            metadata = yaml.safe_load(match.group(1))
        except yaml.YAMLError as e:
            raise PromptError(f"{path}: invalid YAML frontmatter: {e}") from e

        try:
            manifest = PromptManifest.model_validate(metadata)
        except PydanticError as e:
            raise PromptError(f"{path}: frontmatter does not match schema:\n{e}") from e

        if manifest.kind != kind:
            raise PromptError(
                f"{path}: kind mismatch — directory says {kind.value}, "
                f"frontmatter says {manifest.kind.value}"
            )

        if manifest.name != name:
            raise PromptError(
                f"{path}: name mismatch — file is {name}.md, "
                f"frontmatter says {manifest.name!r}"
            )

        return LoadedPrompt(
            manifest=manifest,
            template=match.group(2),
            source_path=str(path),
        )

    def render(
        self,
        kind: PromptKind | str,
        name: str,
        inputs: dict[str, Any],
    ) -> RenderedPrompt:
        loaded = self.load(kind, name)
        manifest = loaded.manifest

        declared = {i.name for i in manifest.inputs}
        provided = set(inputs.keys())

        missing = declared - provided
        if missing:
            raise PromptError(
                f"{loaded.source_path}: missing required inputs: {sorted(missing)}"
            )

        unexpected = provided - declared
        if unexpected:
            raise PromptError(
                f"{loaded.source_path}: unexpected inputs: {sorted(unexpected)}"
            )

        body = _substitute(loaded.template, inputs)
        return RenderedPrompt(manifest=manifest, body=body)

    def validate_response(self, manifest: PromptManifest, response: Any) -> None:
        """Validate an AI response against the manifest's output_schema.

        For `output_schema: string` accepts any string and rejects others.
        For a JSON Schema, runs Draft 2020-12 validation and raises with
        the failing field on mismatch.
        """
        if manifest.output_schema == "string":
            if not isinstance(response, str):
                raise PromptError(
                    f"output_schema is 'string' but response is "
                    f"{type(response).__name__}"
                )
            return

        try:
            Draft202012Validator(manifest.output_schema).validate(response)
        except JsonSchemaError as e:
            path = ".".join(str(p) for p in e.absolute_path) or "<root>"
            raise PromptError(
                f"response failed JSON Schema validation at {path}: {e.message}"
            ) from e


def _substitute(template: str, inputs: dict[str, Any]) -> str:
    def replace(match: re.Match[str]) -> str:
        var = match.group(1)
        if var not in inputs:
            return match.group(0)
        value = inputs[var]
        if isinstance(value, str):
            return value
        return json.dumps(value, indent=2, ensure_ascii=False)

    return _PLACEHOLDER_RE.sub(replace, template)
