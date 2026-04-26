"""initial schema (ai_call)

Revision ID: c4f662aae3bc
Revises: 
Create Date: 2026-04-26 16:52:16.709782

"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4f662aae3bc'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_call",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("model", sa.String(length=64), nullable=False),
        sa.Column("prompt_kind", sa.String(length=16), nullable=True),
        sa.Column("prompt_name", sa.String(length=128), nullable=True),
        sa.Column("prompt_version", sa.Integer(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("cost_usd", sa.Float(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("succeeded", sa.Boolean(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ai_call_created_at"), "ai_call", ["created_at"])
    op.create_index(op.f("ix_ai_call_prompt_name"), "ai_call", ["prompt_name"])


def downgrade() -> None:
    op.drop_index(op.f("ix_ai_call_prompt_name"), table_name="ai_call")
    op.drop_index(op.f("ix_ai_call_created_at"), table_name="ai_call")
    op.drop_table("ai_call")
