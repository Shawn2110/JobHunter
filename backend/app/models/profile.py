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


class Profile(Base):
    """The user's persistent profile.

    Single-row table — JobHunt is a single-user system. The application
    layer enforces that exactly one row exists.
    """

    __tablename__ = "profile"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    headline: Mapped[str | None] = mapped_column(String(255))
    about_me_text: Mapped[str | None] = mapped_column(Text)
    target_seniority: Mapped[str | None] = mapped_column(String(64))

    # JSON: { "IN": "citizen", "US": "needs_sponsorship", ... }
    work_authorization: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    salary_floor: Mapped[int | None] = mapped_column()
    salary_currency: Mapped[str | None] = mapped_column(String(3))  # INR / USD
    notice_period_days: Mapped[int | None] = mapped_column()

    # JSON: { "industries": [...], "company_stages": [...], "free_text": "..." }
    anti_preferences: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.current_timestamp(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
        nullable=False,
    )

    handles: Mapped[list[ProfileHandle]] = relationship(
        back_populates="profile",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class ProfileHandle(Base):
    """A verifiable external handle (GitHub, LeetCode, etc.).

    Per Architecture.md § 3.1 — fetched fresh at search time, not at
    setup. last_signal_json caches the most recent fetch so handle
    refresh is rate-limit-friendly.
    """

    __tablename__ = "profile_handle"
    __table_args__ = (
        UniqueConstraint("profile_id", "kind", name="uq_profile_handle_kind"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("profile.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # github / leetcode / kaggle / linkedin / portfolio
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    username: Mapped[str | None] = mapped_column(String(120))
    url: Mapped[str] = mapped_column(String(512), nullable=False)
    last_fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_signal_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    profile: Mapped[Profile] = relationship(back_populates="handles")
