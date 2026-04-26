"""resume table

Revision ID: 7e13ef2dd222
Revises: f5f3bdeeb327
Create Date: 2026-04-26 17:36:20.222309

"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7e13ef2dd222'
down_revision: str | None = 'f5f3bdeeb327'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "resume",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("source_file_path", sa.String(length=512), nullable=True),
        sa.Column("source_mime_type", sa.String(length=64), nullable=True),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column("parsed_json", sa.JSON(), nullable=True),
        sa.Column("is_master", sa.Boolean(), nullable=False),
        sa.Column("derived_from_id", sa.Integer(), nullable=True),
        sa.Column("label", sa.String(length=120), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["derived_from_id"], ["resume.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_resume_created_at"), "resume", ["created_at"])


def downgrade() -> None:
    op.drop_index(op.f("ix_resume_created_at"), table_name="resume")
    op.drop_table("resume")
