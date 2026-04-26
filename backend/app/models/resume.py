from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Resume(Base):
    """A versioned resume.

    The original upload is the master (`is_master=True`). Tailored
    versions reference the master via `derived_from_id`. The parsed
    structured representation lives in `parsed_json`; the source file
    on disk is referenced by `source_file_path`.
    """

    __tablename__ = "resume"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    source_file_path: Mapped[str | None] = mapped_column(String(512))
    source_mime_type: Mapped[str | None] = mapped_column(String(64))
    raw_text: Mapped[str | None] = mapped_column(Text)
    parsed_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    is_master: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    derived_from_id: Mapped[int | None] = mapped_column(
        ForeignKey("resume.id", ondelete="SET NULL")
    )

    label: Mapped[str | None] = mapped_column(String(120))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.current_timestamp(),
        nullable=False,
        index=True,
    )

    derived_from: Mapped[Resume | None] = relationship(
        "Resume", remote_side="Resume.id", back_populates="derivatives"
    )
    derivatives: Mapped[list[Resume]] = relationship(
        "Resume", back_populates="derived_from"
    )
