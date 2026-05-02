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
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class OutreachDraft(Base):
    """One outreach attempt at one contact for (optionally) one job.

    Per Agent.md § 1: JobHunt never sends outreach automatically.
    sent_manually_at is the user marking that they sent it themselves.
    """

    __tablename__ = "outreach_draft"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    contact_id: Mapped[int] = mapped_column(
        ForeignKey("contact.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job_id: Mapped[int | None] = mapped_column(ForeignKey("job.id", ondelete="SET NULL"))

    # referral | application_support | cold_intro
    intent: Mapped[str] = mapped_column(String(32), nullable=False)
    brief_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    user_edits_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    draft_text: Mapped[str | None] = mapped_column(Text)
    reasoning_text: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.current_timestamp(),
        nullable=False,
    )
    sent_manually_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
