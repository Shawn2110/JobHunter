"""profile and profile_handle

Revision ID: f5f3bdeeb327
Revises: c4f662aae3bc
Create Date: 2026-04-26 17:30:33.633627

"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f5f3bdeeb327'
down_revision: str | None = 'c4f662aae3bc'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "profile",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("headline", sa.String(length=255), nullable=True),
        sa.Column("about_me_text", sa.Text(), nullable=True),
        sa.Column("target_seniority", sa.String(length=64), nullable=True),
        sa.Column("work_authorization", sa.JSON(), nullable=True),
        sa.Column("salary_floor", sa.Integer(), nullable=True),
        sa.Column("salary_currency", sa.String(length=3), nullable=True),
        sa.Column("notice_period_days", sa.Integer(), nullable=True),
        sa.Column("anti_preferences", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "profile_handle",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("username", sa.String(length=120), nullable=True),
        sa.Column("url", sa.String(length=512), nullable=False),
        sa.Column("last_fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_signal_json", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["profile_id"], ["profile.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("profile_id", "kind", name="uq_profile_handle_kind"),
    )
    op.create_index(
        op.f("ix_profile_handle_profile_id"), "profile_handle", ["profile_id"]
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_profile_handle_profile_id"), table_name="profile_handle")
    op.drop_table("profile_handle")
    op.drop_table("profile")
