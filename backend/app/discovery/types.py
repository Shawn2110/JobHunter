from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class SearchInput(BaseModel):
    """User-provided search parameters submitted to the discovery layer."""

    role: str = Field(min_length=1, max_length=255)
    domain: str | None = None
    locations: list[str] = Field(default_factory=list)
    work_mode: Literal["remote", "hybrid", "onsite", "any"] | None = "any"
    salary_floor: int | None = None
    page: int = 1
    per_page: int = 20


class DiscoveredJob(BaseModel):
    """A normalized job record produced by an adapter — not yet persisted."""

    title: str
    company: str
    location: str | None = None
    work_mode: str | None = None
    salary_text: str | None = None
    description_md: str | None = None
    posted_at: datetime | None = None
    apply_url: str | None = None
    source_provider: str  # which adapter produced this row
