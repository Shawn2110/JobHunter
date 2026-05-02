from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class TailoringBrief(Base):
    """Layer-1 output — the tailoring strategy. Editable by the user
    before Layer-2 execution.
    """

    __tablename__ = "tailoring_brief"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    job_id: Mapped[int] = mapped_column(
        ForeignKey("job.id", ondelete="CASCADE"), nullable=False, index=True
    )
    base_resume_id: Mapped[int] = mapped_column(
        ForeignKey("resume.id", ondelete="CASCADE"), nullable=False
    )
    brief_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    user_edits_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.current_timestamp(),
        nullable=False,
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    artifacts: Mapped[list["TailoredArtifact"]] = relationship(
        back_populates="brief", cascade="all, delete-orphan", lazy="selectin"
    )


class TailoredArtifact(Base):
    """Layer-2 output — a generated artifact (resume / cover letter /
    custom-question answer set).
    """

    __tablename__ = "tailored_artifact"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    brief_id: Mapped[int] = mapped_column(
        ForeignKey("tailoring_brief.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # resume / cover_letter / custom_answers
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    content_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    content_md: Mapped[str | None] = mapped_column(Text)
    output_file_path: Mapped[str | None] = mapped_column(String(512))

    truthfulness_passed: Mapped[bool | None] = mapped_column()
    truthfulness_violations_json: Mapped[list[str] | None] = mapped_column(JSON)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.current_timestamp(),
        nullable=False,
    )

    brief: Mapped[TailoringBrief] = relationship(back_populates="artifacts")
