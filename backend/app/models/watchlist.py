from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    DateTime,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class WatchlistCompany(Base):
    """A company on the user's watchlist.

    Phase 9 nightly scheduler reads this table, fetches each
    careers_url, diffs against the local index, and surfaces new
    postings for the next morning.
    """

    __tablename__ = "watchlist_company"
    __table_args__ = (
        UniqueConstraint("careers_url", name="uq_watchlist_company_url"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    careers_url: Mapped[str] = mapped_column(String(1024), nullable=False)

    # Autodetected from careers_url at insert time. Null when the URL
    # didn't match any known ATS host (the crawler will fall back to
    # JSON-LD parsing).
    ats_provider: Mapped[str | None] = mapped_column(String(32))
    ats_slug: Mapped[str | None] = mapped_column(String(120))

    last_crawled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_diff_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_new_count: Mapped[int | None] = mapped_column()

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.current_timestamp(),
        nullable=False,
    )
