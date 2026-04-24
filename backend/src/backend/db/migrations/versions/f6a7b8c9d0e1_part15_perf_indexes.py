"""Part 15 — Performance indexes for hot query paths

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-04-24 18:30:00.000000+00:00
"""
from collections.abc import Sequence

from alembic import op

revision: str = "f6a7b8c9d0e1"
down_revision: str | None = "e5f6a7b8c9d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Audit log — most queries filter by actor and order by occurred_at
    op.create_index(
        "ix_audit_log_actor_occurred",
        "audit_log",
        ["actor_user_id", "occurred_at"],
    )
    op.create_index("ix_audit_log_target", "audit_log", ["target_type", "target_id"])

    # Notifications — admin stats + recipient history
    op.create_index(
        "ix_notifications_recipient_status",
        "notifications",
        ["recipient_user_id", "status"],
    )
    op.create_index("ix_notifications_queued_at", "notifications", ["queued_at"])

    # Enquiries queue filters
    op.create_index("ix_enquiries_status", "enquiries", ["status"])
    op.create_index("ix_enquiries_assigned_staff", "enquiries", ["assigned_staff_id"])

    # Payment attempts — reconciliation + student history
    op.create_index(
        "ix_payment_attempts_user_status",
        "payment_attempts",
        ["user_id", "status"],
    )
    op.create_index(
        "ix_payment_attempts_invoice",
        "payment_attempts",
        ["banner_invoice_id"],
    )

    # Applications queue filter + ordering
    op.create_index(
        "ix_applications_status_submitted",
        "applications",
        ["status", "submitted_at"],
    )

    # Lecturer grades lookup
    op.create_index(
        "ix_lecturer_grades_offering_period",
        "lecturer_grades",
        ["offering_id", "assessment_period"],
    )
    op.create_index(
        "ix_lecturer_grades_student",
        "lecturer_grades",
        ["banner_student_id"],
    )

    # Sessions — lookup by token hash already unique; revocation sweeps use expires_at
    op.create_index("ix_sessions_expires_at", "sessions", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_sessions_expires_at", table_name="sessions")
    op.drop_index("ix_lecturer_grades_student", table_name="lecturer_grades")
    op.drop_index("ix_lecturer_grades_offering_period", table_name="lecturer_grades")
    op.drop_index("ix_applications_status_submitted", table_name="applications")
    op.drop_index("ix_payment_attempts_invoice", table_name="payment_attempts")
    op.drop_index("ix_payment_attempts_user_status", table_name="payment_attempts")
    op.drop_index("ix_enquiries_assigned_staff", table_name="enquiries")
    op.drop_index("ix_enquiries_status", table_name="enquiries")
    op.drop_index("ix_notifications_queued_at", table_name="notifications")
    op.drop_index("ix_notifications_recipient_status", table_name="notifications")
    op.drop_index("ix_audit_log_target", table_name="audit_log")
    op.drop_index("ix_audit_log_actor_occurred", table_name="audit_log")
