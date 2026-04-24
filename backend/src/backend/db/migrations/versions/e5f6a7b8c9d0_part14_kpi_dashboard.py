"""Part 14 — KPI dashboard: direction, description, source columns

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-04-24 12:00:00.000000+00:00
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e5f6a7b8c9d0"
down_revision: str | None = "d4e5f6a7b8c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "kpi_definitions",
        sa.Column(
            "direction",
            sa.Text(),
            nullable=False,
            server_default="higher_better",
        ),
    )
    op.add_column(
        "kpi_definitions",
        sa.Column("description", sa.Text(), nullable=True),
    )
    op.add_column(
        "kpi_definitions",
        sa.Column(
            "source",
            sa.Text(),
            nullable=False,
            server_default="auto",
        ),
    )
    op.create_index(
        "ix_kpi_values_code_period",
        "kpi_values",
        ["kpi_code", "period_start", "period_end"],
    )


def downgrade() -> None:
    op.drop_index("ix_kpi_values_code_period", table_name="kpi_values")
    op.drop_column("kpi_definitions", "source")
    op.drop_column("kpi_definitions", "description")
    op.drop_column("kpi_definitions", "direction")
