from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Contact(Base):
    """A discovered hiring contact at a specific company.

    Per PRD § 3.8 / Agent.md § Hard Refusals:
    - email is opportunistic — only set when found on a public page.
    - email_source records WHERE we found it ("company_about_page",
      "twitter_bio", etc.). No paid email-finder, no SMTP verification.
    - linkedin_url is a Google search result; the user clicks it.
      We never fetch LinkedIn pages.
    """

    __tablename__ = "contact"
    __table_args__ = (
        UniqueConstraint(
            "company_canonical", "linkedin_url", name="uq_contact_company_linkedin"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    company_canonical: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True
    )
    name: Mapped[str | None] = mapped_column(String(255))
    role: Mapped[str | None] = mapped_column(String(255))
    linkedin_url: Mapped[str | None] = mapped_column(String(1024))

    email: Mapped[str | None] = mapped_column(String(320))
    email_source: Mapped[str | None] = mapped_column(String(64))

    signal_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    briefing_md: Mapped[str | None] = mapped_column(Text)

    discovered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.current_timestamp(),
        nullable=False,
    )
    last_refreshed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
