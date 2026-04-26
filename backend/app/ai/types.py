from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class PromptKind(str, Enum):
    """Three prompt kinds — see prompts/__loader__.md."""

    META = "meta"
    EXECUTION = "execution"
    STATIC = "static"


class PromptInput(BaseModel):
    """One declared input variable on a prompt manifest."""

    name: str
    type: Literal["string", "object", "list"]
    description: str = ""


class PromptManifest(BaseModel):
    """Frontmatter shape for every prompt file in prompts/<kind>/."""

    name: str
    kind: PromptKind
    version: int = Field(ge=1)
    inputs: list[PromptInput] = Field(default_factory=list)
    output_schema: dict[str, Any] | Literal["string"] = "string"
    model: str
    max_tokens: int = 4096
    temperature: float = Field(default=0.2, ge=0.0, le=1.0)
    notes: str | None = None


class LoadedPrompt(BaseModel):
    """A prompt parsed from disk — manifest + raw template body."""

    manifest: PromptManifest
    template: str
    source_path: str


class RenderedPrompt(BaseModel):
    """A loaded prompt with its template substituted from inputs."""

    manifest: PromptManifest
    body: str
