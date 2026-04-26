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


class FitAssessment(Base):
    """Per-(job × profile) multi-dimensional fit verdict.

    Single profile in v1, so one row per Job. PRD § 3.4 / Architecture
    § 4. Verdict is one of: strong / good / stretch / below / mismatch.
    """

    __tablename__ = "fit_assessment"
    __table_args__ = (UniqueConstraint("job_id", name="uq_fit_assessment_job"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    job_id: Mapped[int] = mapped_column(
        ForeignKey("job.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # { "present": [...], "missing": [...], "score_required": "7/10" }
    skills_match_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    experience_verdict: Mapped[str | None] = mapped_column(String(255))
    domain_match: Mapped[str | None] = mapped_column(String(255))
    evidence_strength: Mapped[str | None] = mapped_column(String(255))

    # [{ "question": "...", "criterion": "...", "user_status": "...", "can_pass": "yes/no/maybe" }]
    knockout_risks_json: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON)

    verdict: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    summary_md: Mapped[str | None] = mapped_column(Text)

    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.current_timestamp(),
        nullable=False,
    )

    job = relationship("Job")
