"""tailoring brief.kind + artifact.brief_id nullable + job_id

Revision ID: 0c53d61809c6
Revises: 2f5dcc837dcb
Create Date: 2026-05-03 19:47:44.190450

SQLite needs special handling for FK changes. The tailored_artifact
table is rebuilt from scratch since cover-letter and custom-question
flows need a nullable brief_id and a direct job_id reference.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0c53d61809c6"
down_revision: str | None = "2f5dcc837dcb"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # tailoring_brief: add `kind` column
    with op.batch_alter_table("tailoring_brief") as batch:
        batch.add_column(
            sa.Column(
                "kind",
                sa.String(length=32),
                server_default="resume",
                nullable=False,
            )
        )
    op.create_index(
        op.f("ix_tailoring_brief_kind"), "tailoring_brief", ["kind"]
    )

    # tailored_artifact: rebuild table. Existing rows are preserved
    # via INSERT…SELECT; if there are none, the rebuild is just DDL.
    op.execute("ALTER TABLE tailored_artifact RENAME TO tailored_artifact_old")

    op.create_table(
        "tailored_artifact",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("brief_id", sa.Integer(), nullable=True),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("content_json", sa.JSON(), nullable=True),
        sa.Column("content_md", sa.Text(), nullable=True),
        sa.Column("output_file_path", sa.String(length=512), nullable=True),
        sa.Column("truthfulness_passed", sa.Boolean(), nullable=True),
        sa.Column("truthfulness_violations_json", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["job.id"],
            ondelete="CASCADE",
            name="fk_tailored_artifact_job",
        ),
        sa.ForeignKeyConstraint(
            ["brief_id"],
            ["tailoring_brief.id"],
            ondelete="SET NULL",
            name="fk_tailored_artifact_brief",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Backfill from old rows: pull job_id from the linked brief.
    op.execute(
        """
        INSERT INTO tailored_artifact (
            id, job_id, brief_id, kind, content_json, content_md,
            output_file_path, truthfulness_passed,
            truthfulness_violations_json, created_at
        )
        SELECT
            old.id,
            (SELECT job_id FROM tailoring_brief WHERE tailoring_brief.id = old.brief_id),
            old.brief_id,
            old.kind,
            old.content_json,
            old.content_md,
            old.output_file_path,
            old.truthfulness_passed,
            old.truthfulness_violations_json,
            old.created_at
        FROM tailored_artifact_old old
        """
    )

    op.execute("DROP TABLE tailored_artifact_old")

    op.create_index(
        op.f("ix_tailored_artifact_job_id"), "tailored_artifact", ["job_id"]
    )
    op.create_index(
        op.f("ix_tailored_artifact_brief_id"), "tailored_artifact", ["brief_id"]
    )
    op.create_index(
        op.f("ix_tailored_artifact_kind"), "tailored_artifact", ["kind"]
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_tailored_artifact_kind"), table_name="tailored_artifact")
    op.drop_index(op.f("ix_tailored_artifact_brief_id"), table_name="tailored_artifact")
    op.drop_index(op.f("ix_tailored_artifact_job_id"), table_name="tailored_artifact")

    op.execute("ALTER TABLE tailored_artifact RENAME TO tailored_artifact_new")
    op.create_table(
        "tailored_artifact",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("brief_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("content_json", sa.JSON(), nullable=True),
        sa.Column("content_md", sa.Text(), nullable=True),
        sa.Column("output_file_path", sa.String(length=512), nullable=True),
        sa.Column("truthfulness_passed", sa.Boolean(), nullable=True),
        sa.Column("truthfulness_violations_json", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["brief_id"], ["tailoring_brief.id"], ondelete="CASCADE",
            name="fk_tailored_artifact_brief",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute(
        """
        INSERT INTO tailored_artifact (
            id, brief_id, kind, content_json, content_md,
            output_file_path, truthfulness_passed,
            truthfulness_violations_json, created_at
        )
        SELECT id, brief_id, kind, content_json, content_md,
               output_file_path, truthfulness_passed,
               truthfulness_violations_json, created_at
        FROM tailored_artifact_new
        WHERE brief_id IS NOT NULL
        """
    )
    op.execute("DROP TABLE tailored_artifact_new")
    op.create_index(
        op.f("ix_tailored_artifact_brief_id"), "tailored_artifact", ["brief_id"]
    )

    op.drop_index(op.f("ix_tailoring_brief_kind"), table_name="tailoring_brief")
    with op.batch_alter_table("tailoring_brief") as batch:
        batch.drop_column("kind")
