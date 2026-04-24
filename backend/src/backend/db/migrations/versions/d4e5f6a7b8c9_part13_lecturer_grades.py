"""Part 13 — lecturer grade drafts workflow table

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-04-24 09:00:00.000000+00:00
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d4e5f6a7b8c9"
down_revision: str | None = "c3d4e5f6a7b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "lecturer_grades",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("offering_id", sa.Text(), nullable=False),
        sa.Column("course_code", sa.Text(), nullable=False),
        sa.Column("banner_student_id", sa.Text(), nullable=False),
        sa.Column("semester", sa.Text(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column(
            "assessment_period",
            sa.Text(),
            nullable=False,
            server_default="final",
        ),
        sa.Column("grade", sa.Text()),
        sa.Column("status", sa.Text(), nullable=False, server_default="draft"),
        sa.Column(
            "entered_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
        ),
        sa.Column("submitted_at", sa.DateTime(timezone=True)),
        sa.Column("finalised_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "offering_id",
            "banner_student_id",
            "assessment_period",
            name="uq_lecturer_grades_offering_student_period",
        ),
    )
    op.create_index(
        "ix_lecturer_grades_offering",
        "lecturer_grades",
        ["offering_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_lecturer_grades_offering", table_name="lecturer_grades")
    op.drop_table("lecturer_grades")
