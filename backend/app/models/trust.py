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


class TrustAssessment(Base):
    """Per-job trust verdict per PRD § 3.9 / Architecture § 5.6.

    verdict ∈ {verified, likely_real, suspicious, likely_scam, unknown}.
    Always informational — never used to gatekeep jobs out of the feed.
    """

    __tablename__ = "trust_assessment"
    __table_args__ = (UniqueConstraint("job_id", name="uq_trust_assessment_job"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    job_id: Mapped[int] = mapped_column(
        ForeignKey("job.id", ondelete="CASCADE"), nullable=False, index=True
    )

    verdict: Mapped[str] = mapped_column(String(16), nullable=False, index=True)

    scam_signals_json: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON)
    ghost_job_signals_json: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON)
    positive_signals_json: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON)
    rationale_md: Mapped[str | None] = mapped_column(Text)

    static_check_score: Mapped[int | None] = mapped_column()  # 0-100, lower = more flags
    ai_check_score: Mapped[int | None] = mapped_column()      # 0-100
    longitudinal_score: Mapped[int | None] = mapped_column()  # 0-100, null when no history

    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.current_timestamp(),
        nullable=False,
    )

    job = relationship("Job", back_populates="trust_assessment")


class JobRepostHistory(Base):
    """Repost history powering Layer C (longitudinal) trust signals.

    One row per ingestion event for a canonical job. Same company +
    similar title + similar description hash to itself → same canonical
    bucket → reposts visible at query time.
    """

    __tablename__ = "job_repost_history"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    job_canonical_id: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.current_timestamp(),
        nullable=False,
        index=True,
    )
    source_url: Mapped[str | None] = mapped_column(String(1024))
    description_hash: Mapped[str | None] = mapped_column(String(64))
    company_canonical: Mapped[str | None] = mapped_column(String(255), index=True)
    title_normalized: Mapped[str | None] = mapped_column(String(255))
