from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class AiCall(Base):
    """One row per Claude API call.

    Powers the cost dashboard (P10-T2) and serves as the audit trail for
    every AI output the user sees. Never stores prompt or response
    bodies — only metadata, so the table stays small and never holds
    sensitive content.
    """

    __tablename__ = "ai_call"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.current_timestamp(),
        nullable=False,
        index=True,
    )

    model: Mapped[str] = mapped_column(String(64), nullable=False)

    prompt_kind: Mapped[str | None] = mapped_column(String(16))
    prompt_name: Mapped[str | None] = mapped_column(String(128), index=True)
    prompt_version: Mapped[int | None] = mapped_column()

    input_tokens: Mapped[int] = mapped_column(default=0, nullable=False)
    output_tokens: Mapped[int] = mapped_column(default=0, nullable=False)
    cost_usd: Mapped[float | None] = mapped_column()

    duration_ms: Mapped[int | None] = mapped_column()

    succeeded: Mapped[bool] = mapped_column(default=True, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
