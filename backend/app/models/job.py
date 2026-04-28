from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Job(Base):
    """A job posting — canonical representation across all sources.

    The same role appearing on JSearch + Adzuna + a careers page becomes
    one Job with three JobSource rows.
    """

    __tablename__ = "job"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    company: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    company_canonical: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True
    )

    location: Mapped[str | None] = mapped_column(String(255))
    work_mode: Mapped[str | None] = mapped_column(String(32))  # remote/hybrid/onsite
    salary_text: Mapped[str | None] = mapped_column(String(255))

    description_md: Mapped[str | None] = mapped_column(Text)
    requirements_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    apply_url: Mapped[str | None] = mapped_column(String(1024))
    ats_family: Mapped[str | None] = mapped_column(String(32))

    embedding_id: Mapped[str | None] = mapped_column(String(64))
    embedding_vector: Mapped[list[float] | None] = mapped_column(JSON)

    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.current_timestamp(),
        nullable=False,
        index=True,
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
        nullable=False,
    )

    sources: Mapped[list[JobSource]] = relationship(
        back_populates="job", cascade="all, delete-orphan", lazy="selectin"
    )
    fit_assessment: Mapped["FitAssessment | None"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "FitAssessment",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="selectin",
        back_populates="job",
    )


class JobSource(Base):
    """Where a Job was discovered. Many-to-one with Job."""

    __tablename__ = "job_source"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    job_id: Mapped[int] = mapped_column(
        ForeignKey("job.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # aggregator / founder_post / careers_page
    source_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    # jsearch / adzuna / jooble / wellfound / company_url / ...
    source_provider: Mapped[str] = mapped_column(String(64), nullable=False)
    source_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.current_timestamp(),
        nullable=False,
    )

    job: Mapped[Job] = relationship(back_populates="sources")


class SearchQuery(Base):
    """A saved search the user runs repeatedly. Powers the diff feed."""

    __tablename__ = "search_query"
    __table_args__ = (UniqueConstraint("name", name="uq_search_query_name"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    role: Mapped[str] = mapped_column(String(255), nullable=False)
    domain: Mapped[str | None] = mapped_column(String(255))
    locations_json: Mapped[list[str] | None] = mapped_column(JSON)
    work_mode: Mapped[str | None] = mapped_column(String(32))
    salary_floor: Mapped[int | None] = mapped_column()
    modes_enabled_json: Mapped[list[str] | None] = mapped_column(JSON)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.current_timestamp(),
        nullable=False,
    )
