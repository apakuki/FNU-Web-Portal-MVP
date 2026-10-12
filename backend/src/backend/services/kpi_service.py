"""KPI computation service (Part 14).

Compute functions read portal transactional data — applications, payments,
enquiries, chatbot, lecturer grades — and upsert a row into `kpi_values`
per KPI code per period. Auto-computed KPIs use `source="auto"`; manual
entries use `source="manual"`.

`run_all` drives the full compute pass; it is invoked both by the
scheduler job (Part 14) and the admin-triggered `POST /api/admin/kpi/compute`
endpoint so results are identical.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from decimal import Decimal

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.backend.banner import get_banner_client
from src.backend.db.models import (
    Application,
    ChatbotConversation,
    Enquiry,
    KpiDefinition,
    KpiValue,
    LecturerGrade,
    PaymentAttempt,
    User,
)

logger = logging.getLogger(__name__)


# --- Period helpers --------------------------------------------------------


@dataclass(frozen=True)
class Period:
    start: date
    end: date

    @property
    def start_dt(self) -> datetime:
        return datetime.combine(self.start, time.min, tzinfo=UTC)

    @property
    def end_dt(self) -> datetime:
        return datetime.combine(self.end, time.max, tzinfo=UTC)


def current_semester_period(today: date | None = None) -> Period:
    """Return the current FNU semester period (S1: Feb–Jun, S2: Jul–Nov)."""
    today = today or datetime.now(UTC).date()
    if today.month <= 6:
        return Period(date(today.year, 2, 1), date(today.year, 6, 30))
    return Period(date(today.year, 7, 1), date(today.year, 11, 30))


def ytd_period(today: date | None = None) -> Period:
    today = today or datetime.now(UTC).date()
    return Period(date(today.year, 1, 1), today)


# --- Compute primitives ---------------------------------------------------


async def _upsert_value(
    db: AsyncSession,
    *,
    kpi_code: str,
    period: Period,
    value: float,
    source: str = "auto",
    target: float | None = None,
    staff_user_id: uuid.UUID | None = None,
    college: str | None = None,
    function: str | None = None,
) -> KpiValue:
    """Replace any existing row for (code, period, scope) and insert the new value."""
    await db.execute(
        delete(KpiValue).where(
            KpiValue.kpi_code == kpi_code,
            KpiValue.period_start == period.start,
            KpiValue.period_end == period.end,
            KpiValue.staff_user_id == staff_user_id,
            KpiValue.college == college,
            KpiValue.function == function,
            KpiValue.source == source,
        )
    )
    row = KpiValue(
        kpi_code=kpi_code,
        period_start=period.start,
        period_end=period.end,
        value=value,
        target=target,
        source=source,
        staff_user_id=staff_user_id,
        college=college,
        function=function,
    )
    db.add(row)
    return row


async def _target_for(db: AsyncSession, code: str) -> float | None:
    raw = await db.scalar(
        select(KpiDefinition.target_default).where(KpiDefinition.code == code)
    )
    return float(raw) if raw is not None else None


# --- Compute functions ----------------------------------------------------


async def compute_enrolment(db: AsyncSession, period: Period) -> None:
    active = await db.scalar(
        select(func.count())
        .select_from(User)
        .where(User.role == "student", User.is_active.is_(True))
    ) or 0
    await _upsert_value(
        db,
        kpi_code="enrolment.active_students",
        period=period,
        value=float(active),
        target=await _target_for(db, "enrolment.active_students"),
    )

    new_apps = await db.scalar(
        select(func.count())
        .select_from(Application)
        .where(
            Application.submitted_at >= period.start_dt,
            Application.submitted_at <= period.end_dt,
        )
    ) or 0
    await _upsert_value(
        db,
        kpi_code="enrolment.new_applications",
        period=period,
        value=float(new_apps),
        target=await _target_for(db, "enrolment.new_applications"),
    )


async def compute_applications(db: AsyncSession, period: Period) -> None:
    decided_rows = (
        await db.scalars(
            select(Application).where(
                Application.decided_at.is_not(None),
                Application.decided_at >= period.start_dt,
                Application.decided_at <= period.end_dt,
            )
        )
    ).all()

    if decided_rows:
        total_seconds = 0.0
        approved = 0
        for a in decided_rows:
            if a.decided_at is None:
                continue
            total_seconds += (a.decided_at - a.submitted_at).total_seconds()
            if a.status == "approved":
                approved += 1
        avg_hours = (total_seconds / len(decided_rows)) / 3600.0
        approval_rate = 100.0 * approved / len(decided_rows)
    else:
        avg_hours = 0.0
        approval_rate = 0.0

    await _upsert_value(
        db,
        kpi_code="applications.avg_decision_hours",
        period=period,
        value=round(avg_hours, 2),
        target=await _target_for(db, "applications.avg_decision_hours"),
    )
    await _upsert_value(
        db,
        kpi_code="applications.approval_rate",
        period=period,
        value=round(approval_rate, 2),
        target=await _target_for(db, "applications.approval_rate"),
    )


async def compute_payments(db: AsyncSession, period: Period) -> None:
    confirmed_rows = (
        await db.scalars(
            select(PaymentAttempt).where(
                PaymentAttempt.status == "confirmed",
                PaymentAttempt.updated_at >= period.start_dt,
                PaymentAttempt.updated_at <= period.end_dt,
            )
        )
    ).all()
    total_fjd = sum(p.amount_cents for p in confirmed_rows) / 100.0
    await _upsert_value(
        db,
        kpi_code="payments.total_collected_fjd",
        period=period,
        value=round(total_fjd, 2),
        target=await _target_for(db, "payments.total_collected_fjd"),
    )
    await _upsert_value(
        db,
        kpi_code="payments.count_confirmed",
        period=period,
        value=float(len(confirmed_rows)),
        target=await _target_for(db, "payments.count_confirmed"),
    )

    banner = get_banner_client()
    total_outstanding_cents = 0
    student_users = (
        await db.scalars(
            select(User).where(User.role == "student", User.banner_id.is_not(None))
        )
    ).all()
    for u in student_users:
        invoices = await banner.get_invoices(u.banner_id)  # type: ignore[arg-type]
        for inv in invoices:
            total_outstanding_cents += max(0, inv.total_cents - inv.paid_cents)
    await _upsert_value(
        db,
        kpi_code="payments.outstanding_balance_fjd",
        period=period,
        value=round(total_outstanding_cents / 100.0, 2),
        target=await _target_for(db, "payments.outstanding_balance_fjd"),
    )


async def compute_enquiries(db: AsyncSession, period: Period) -> None:
    resolved_rows = (
        await db.scalars(
            select(Enquiry).where(
                Enquiry.resolved_at.is_not(None),
                Enquiry.resolved_at >= period.start_dt,
                Enquiry.resolved_at <= period.end_dt,
            )
        )
    ).all()
    if resolved_rows:
        total_seconds = sum(
            (e.resolved_at - e.opened_at).total_seconds()
            for e in resolved_rows
            if e.resolved_at is not None
        )
        avg_hours = (total_seconds / len(resolved_rows)) / 3600.0
    else:
        avg_hours = 0.0
    await _upsert_value(
        db,
        kpi_code="enquiries.avg_resolution_hours",
        period=period,
        value=round(avg_hours, 2),
        target=await _target_for(db, "enquiries.avg_resolution_hours"),
    )
    await _upsert_value(
        db,
        kpi_code="enquiries.resolved_count",
        period=period,
        value=float(len(resolved_rows)),
        target=await _target_for(db, "enquiries.resolved_count"),
    )


async def compute_chatbot(db: AsyncSession, period: Period) -> None:
    total = await db.scalar(
        select(func.count())
        .select_from(ChatbotConversation)
        .where(
            ChatbotConversation.created_at >= period.start_dt,
            ChatbotConversation.created_at <= period.end_dt,
        )
    ) or 0
    escalated = await db.scalar(
        select(func.count())
        .select_from(ChatbotConversation)
        .where(
            ChatbotConversation.created_at >= period.start_dt,
            ChatbotConversation.created_at <= period.end_dt,
            ChatbotConversation.escalated.is_(True),
        )
    ) or 0
    await _upsert_value(
        db,
        kpi_code="chatbot.total_queries",
        period=period,
        value=float(total),
        target=await _target_for(db, "chatbot.total_queries"),
    )
    rate = (100.0 * escalated / total) if total else 0.0
    await _upsert_value(
        db,
        kpi_code="chatbot.escalation_rate",
        period=period,
        value=round(rate, 2),
        target=await _target_for(db, "chatbot.escalation_rate"),
    )


async def compute_grading(db: AsyncSession, period: Period) -> None:
    finalised = await db.scalar(
        select(func.count())
        .select_from(LecturerGrade)
        .where(
            LecturerGrade.finalised_at.is_not(None),
            LecturerGrade.finalised_at >= period.start_dt,
            LecturerGrade.finalised_at <= period.end_dt,
        )
    ) or 0
    await _upsert_value(
        db,
        kpi_code="grading.finalised_count",
        period=period,
        value=float(finalised),
        target=await _target_for(db, "grading.finalised_count"),
    )


async def run_all(db: AsyncSession, period: Period | None = None) -> Period:
    """Run the full compute pass and commit. Returns the period used."""
    period = period or current_semester_period()
    logger.info("KPI compute run for %s → %s", period.start, period.end)
    await compute_enrolment(db, period)
    await compute_applications(db, period)
    await compute_payments(db, period)
    await compute_enquiries(db, period)
    await compute_chatbot(db, period)
    await compute_grading(db, period)
    await db.commit()
    return period


# --- Traffic-light helper -------------------------------------------------


def traffic_light(value: float, target: float | None, direction: str) -> str:
    """Return "green" | "amber" | "red" based on value vs target + direction.

    `higher_better`: green ≥ target; amber ≥ 80% of target; red otherwise.
    `lower_better`:  green ≤ target; amber ≤ 120% of target; red otherwise.
    Returns "grey" if target is unset.
    """
    if target is None:
        return "grey"
    if direction == "lower_better":
        if value <= target:
            return "green"
        if value <= target * 1.2:
            return "amber"
        return "red"
    # higher_better (default)
    if value >= target:
        return "green"
    if value >= target * 0.8:
        return "amber"
    return "red"


# --- Manual input helper --------------------------------------------------


async def record_manual_value(
    db: AsyncSession,
    *,
    kpi_code: str,
    period: Period,
    value: float,
    staff_user_id: uuid.UUID | None = None,
    college: str | None = None,
    function: str | None = None,
) -> KpiValue:
    target = await _target_for(db, kpi_code)
    row = await _upsert_value(
        db,
        kpi_code=kpi_code,
        period=period,
        value=value,
        source="manual",
        target=target,
        staff_user_id=staff_user_id,
        college=college,
        function=function,
    )
    await db.commit()
    await db.refresh(row)
    return row


# Re-export Decimal for type hints used by callers if needed
__all__ = [
    "Period",
    "current_semester_period",
    "ytd_period",
    "run_all",
    "traffic_light",
    "record_manual_value",
    "Decimal",
]
