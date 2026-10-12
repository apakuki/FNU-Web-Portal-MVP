"""KPI dashboard API (Part 14).

Endpoints power five role-based dashboards — VC/SLT, Dean/Manager,
Section Head, Individual Staff, Finance — plus the administrative
pathway for editing targets and recording manual KPI values.

Recompute can be triggered manually (`POST /api/admin/kpi/compute`); the
scheduler also runs the same pass periodically (see `main.py` lifespan).
"""

from __future__ import annotations

import csv
import io
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.backend.auth import require_role
from src.backend.db.models import Enquiry, KpiDefinition, KpiValue, User
from src.backend.db.session import get_session
from src.backend.services.audit_service import write_audit_log
from src.backend.services.kpi_service import (
    Period,
    current_semester_period,
    record_manual_value,
    run_all,
    traffic_light,
    ytd_period,
)

router = APIRouter(tags=["kpi"])

VALID_PRESETS = {"current_semester", "ytd", "custom"}


# --- Schemas ---------------------------------------------------------------


class KpiDefinitionOut(BaseModel):
    code: str
    name: str
    category: str
    unit: str
    applies_to_role: str
    target_default: float | None
    direction: str
    description: str | None
    source: str
    is_active: bool


class TargetUpdateRequest(BaseModel):
    target_default: float | None = Field(default=None, ge=0)


class KpiValueOut(BaseModel):
    kpi_code: str
    name: str
    category: str
    unit: str
    direction: str
    value: float
    target: float | None
    status: str
    source: str
    period_start: date
    period_end: date
    college: str | None = None
    function: str | None = None
    staff_user_id: uuid.UUID | None = None


class DashboardCard(BaseModel):
    code: str
    name: str
    category: str
    unit: str
    direction: str
    value: float
    target: float | None
    status: str


class DashboardResponse(BaseModel):
    view: str
    period_start: date
    period_end: date
    generated_at: datetime
    cards: list[DashboardCard]


class ManualEntryRequest(BaseModel):
    kpi_code: str = Field(min_length=1, max_length=80)
    value: float
    period_start: date
    period_end: date
    college: str | None = Field(default=None, max_length=80)
    function: str | None = Field(default=None, max_length=80)


class ComputeRunResponse(BaseModel):
    period_start: date
    period_end: date
    ran_at: datetime


class HistoryPoint(BaseModel):
    period_start: date
    period_end: date
    value: float


# --- Helpers --------------------------------------------------------------


def _resolve_period(
    preset: str, period_start: date | None, period_end: date | None
) -> Period:
    if preset == "ytd":
        return ytd_period()
    if preset == "custom":
        if not (period_start and period_end) or period_start > period_end:
            raise HTTPException(
                status_code=400,
                detail="period_start and period_end are required for custom preset",
            )
        if (period_end - period_start).days > 366:
            raise HTTPException(
                status_code=400, detail="Date range cannot exceed 366 days"
            )
        return Period(period_start, period_end)
    # default = current_semester
    return current_semester_period()


async def _latest_value(
    db: AsyncSession, code: str, period: Period, source: str = "auto"
) -> KpiValue | None:
    value: KpiValue | None = await db.scalar(
        select(KpiValue)
        .where(
            KpiValue.kpi_code == code,
            KpiValue.period_start == period.start,
            KpiValue.period_end == period.end,
            KpiValue.source == source,
            KpiValue.staff_user_id.is_(None),
            KpiValue.college.is_(None),
            KpiValue.function.is_(None),
        )
        .order_by(KpiValue.recorded_at.desc())
    )
    return value


async def _definition(db: AsyncSession, code: str) -> KpiDefinition | None:
    defn: KpiDefinition | None = await db.scalar(
        select(KpiDefinition).where(KpiDefinition.code == code)
    )
    return defn


async def _build_cards(
    db: AsyncSession, period: Period, codes: list[str]
) -> list[DashboardCard]:
    cards: list[DashboardCard] = []
    for code in codes:
        defn = await _definition(db, code)
        if not defn or not defn.is_active:
            continue
        row = await _latest_value(db, code, period, source=defn.source)
        value = float(row.value) if row else 0.0
        target = float(row.target) if row and row.target is not None else (
            float(defn.target_default) if defn.target_default is not None else None
        )
        cards.append(
            DashboardCard(
                code=code,
                name=defn.name,
                category=defn.category,
                unit=defn.unit,
                direction=defn.direction,
                value=value,
                target=target,
                status=traffic_light(value, target, defn.direction),
            )
        )
    return cards


VC_CODES = [
    "enrolment.active_students",
    "enrolment.new_applications",
    "applications.avg_decision_hours",
    "applications.approval_rate",
    "payments.total_collected_fjd",
    "payments.outstanding_balance_fjd",
    "enquiries.avg_resolution_hours",
    "chatbot.total_queries",
    "chatbot.escalation_rate",
    "grading.finalised_count",
]

DEAN_CODES = [
    "enrolment.new_applications",
    "applications.avg_decision_hours",
    "applications.approval_rate",
    "enquiries.resolved_count",
    "enquiries.avg_resolution_hours",
    "grading.finalised_count",
]

SECTION_HEAD_CODES = [
    "enquiries.resolved_count",
    "enquiries.avg_resolution_hours",
    "chatbot.escalation_rate",
    "applications.avg_decision_hours",
    "staff.training_hours",
    "staff.satisfaction_score",
]

FINANCE_CODES = [
    "payments.total_collected_fjd",
    "payments.count_confirmed",
    "payments.outstanding_balance_fjd",
]

ME_CODES = [
    "enquiries.resolved_count",
    "applications.avg_decision_hours",
]


# --- Definition + target endpoints ----------------------------------------


@router.get("/api/admin/kpi/definitions", response_model=list[KpiDefinitionOut])
async def list_definitions(
    _user: User = Depends(require_role("staff", "admin", "manager", "vc", "finance")),
    db: AsyncSession = Depends(get_session),
) -> list[KpiDefinitionOut]:
    rows = (
        await db.scalars(select(KpiDefinition).order_by(KpiDefinition.category, KpiDefinition.code))
    ).all()
    return [
        KpiDefinitionOut(
            code=r.code,
            name=r.name,
            category=r.category,
            unit=r.unit,
            applies_to_role=r.applies_to_role,
            target_default=float(r.target_default) if r.target_default is not None else None,
            direction=r.direction,
            description=r.description,
            source=r.source,
            is_active=r.is_active,
        )
        for r in rows
    ]


@router.put("/api/admin/kpi/definitions/{code}/target", response_model=KpiDefinitionOut)
async def update_target(
    code: str,
    body: TargetUpdateRequest,
    request: Request,
    admin: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_session),
) -> KpiDefinitionOut:
    defn = await _definition(db, code)
    if not defn:
        raise HTTPException(status_code=404, detail="KPI not found")

    before = {
        "target_default": (
            float(defn.target_default) if defn.target_default is not None else None
        )
    }
    defn.target_default = (
        Decimal(str(body.target_default)) if body.target_default is not None else None
    )
    await db.commit()
    await db.refresh(defn)

    await write_audit_log(
        actor_user_id=admin.id,
        action="kpi.target.update",
        target_type="kpi_definition",
        target_id=code,
        before=before,
        after={"target_default": body.target_default},
        ip_address=request.client.host if request.client else None,
    )

    return KpiDefinitionOut(
        code=defn.code,
        name=defn.name,
        category=defn.category,
        unit=defn.unit,
        applies_to_role=defn.applies_to_role,
        target_default=float(defn.target_default) if defn.target_default is not None else None,
        direction=defn.direction,
        description=defn.description,
        source=defn.source,
        is_active=defn.is_active,
    )


# --- Value + history endpoints --------------------------------------------


@router.get("/api/admin/kpi/values", response_model=list[KpiValueOut])
async def list_values(
    kpi_code: str | None = None,
    preset: str = "current_semester",
    period_start: date | None = None,
    period_end: date | None = None,
    _user: User = Depends(require_role("staff", "admin", "manager", "vc", "finance")),
    db: AsyncSession = Depends(get_session),
) -> list[KpiValueOut]:
    if preset not in VALID_PRESETS:
        raise HTTPException(status_code=400, detail="Invalid preset")
    period = _resolve_period(preset, period_start, period_end)

    stmt = select(KpiValue, KpiDefinition).join(
        KpiDefinition, KpiDefinition.code == KpiValue.kpi_code
    ).where(
        KpiValue.period_start == period.start,
        KpiValue.period_end == period.end,
    )
    if kpi_code:
        stmt = stmt.where(KpiValue.kpi_code == kpi_code)
    stmt = stmt.order_by(KpiDefinition.category, KpiValue.kpi_code)

    rows = (await db.execute(stmt)).all()
    result: list[KpiValueOut] = []
    for value_row, defn in rows:
        target = (
            float(value_row.target)
            if value_row.target is not None
            else (float(defn.target_default) if defn.target_default is not None else None)
        )
        result.append(
            KpiValueOut(
                kpi_code=value_row.kpi_code,
                name=defn.name,
                category=defn.category,
                unit=defn.unit,
                direction=defn.direction,
                value=float(value_row.value),
                target=target,
                status=traffic_light(float(value_row.value), target, defn.direction),
                source=value_row.source,
                period_start=value_row.period_start,
                period_end=value_row.period_end,
                college=value_row.college,
                function=value_row.function,
                staff_user_id=value_row.staff_user_id,
            )
        )
    return result


@router.get("/api/admin/kpi/history/{code}", response_model=list[HistoryPoint])
async def value_history(
    code: str,
    limit: int = 12,
    _user: User = Depends(require_role("staff", "admin", "manager", "vc", "finance")),
    db: AsyncSession = Depends(get_session),
) -> list[HistoryPoint]:
    if limit < 1 or limit > 100:
        raise HTTPException(status_code=400, detail="limit must be 1..100")
    rows = (
        await db.execute(
            select(KpiValue)
            .where(
                KpiValue.kpi_code == code,
                KpiValue.staff_user_id.is_(None),
                KpiValue.college.is_(None),
                KpiValue.function.is_(None),
            )
            .order_by(KpiValue.period_start.desc())
            .limit(limit)
        )
    ).scalars().all()
    return [
        HistoryPoint(
            period_start=r.period_start,
            period_end=r.period_end,
            value=float(r.value),
        )
        for r in reversed(rows)
    ]


# --- Compute + manual entry -----------------------------------------------


@router.post("/api/admin/kpi/compute", response_model=ComputeRunResponse)
async def trigger_compute(
    preset: str = "current_semester",
    period_start: date | None = None,
    period_end: date | None = None,
    admin: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_session),
) -> ComputeRunResponse:
    if preset not in VALID_PRESETS:
        raise HTTPException(status_code=400, detail="Invalid preset")
    period = _resolve_period(preset, period_start, period_end)
    await run_all(db, period)
    await write_audit_log(
        actor_user_id=admin.id,
        action="kpi.compute",
        target_type="kpi_run",
        target_id=f"{period.start}:{period.end}",
        after={"period_start": str(period.start), "period_end": str(period.end)},
    )
    return ComputeRunResponse(
        period_start=period.start,
        period_end=period.end,
        ran_at=datetime.now(UTC),
    )


@router.post("/api/admin/kpi/manual", response_model=KpiValueOut, status_code=201)
async def manual_entry(
    body: ManualEntryRequest,
    request: Request,
    user: User = Depends(require_role("manager", "admin", "staff")),
    db: AsyncSession = Depends(get_session),
) -> KpiValueOut:
    defn = await _definition(db, body.kpi_code)
    if not defn:
        raise HTTPException(status_code=404, detail="KPI not found")
    if defn.source != "manual":
        raise HTTPException(status_code=400, detail="KPI does not accept manual input")
    if body.period_start > body.period_end:
        raise HTTPException(status_code=400, detail="period_start must be <= period_end")
    if (body.period_end - body.period_start).days > 366:
        raise HTTPException(status_code=400, detail="Date range cannot exceed 366 days")

    row = await record_manual_value(
        db,
        kpi_code=body.kpi_code,
        period=Period(body.period_start, body.period_end),
        value=body.value,
        staff_user_id=user.id if defn.applies_to_role == "staff" else None,
        college=body.college,
        function=body.function,
    )

    await write_audit_log(
        actor_user_id=user.id,
        action="kpi.manual.record",
        target_type="kpi_value",
        target_id=body.kpi_code,
        after={
            "kpi_code": body.kpi_code,
            "value": body.value,
            "period_start": str(body.period_start),
            "period_end": str(body.period_end),
            "college": body.college,
            "function": body.function,
        },
        ip_address=request.client.host if request.client else None,
    )

    target = float(row.target) if row.target is not None else (
        float(defn.target_default) if defn.target_default is not None else None
    )
    return KpiValueOut(
        kpi_code=row.kpi_code,
        name=defn.name,
        category=defn.category,
        unit=defn.unit,
        direction=defn.direction,
        value=float(row.value),
        target=target,
        status=traffic_light(float(row.value), target, defn.direction),
        source=row.source,
        period_start=row.period_start,
        period_end=row.period_end,
        college=row.college,
        function=row.function,
        staff_user_id=row.staff_user_id,
    )


# --- Role-based dashboards ------------------------------------------------


async def _dashboard(
    db: AsyncSession, view: str, codes: list[str], period: Period
) -> DashboardResponse:
    cards = await _build_cards(db, period, codes)
    return DashboardResponse(
        view=view,
        period_start=period.start,
        period_end=period.end,
        generated_at=datetime.now(UTC),
        cards=cards,
    )


def _period_dep(
    preset: str = "current_semester",
    period_start: date | None = None,
    period_end: date | None = None,
) -> Period:
    if preset not in VALID_PRESETS:
        raise HTTPException(status_code=400, detail="Invalid preset")
    return _resolve_period(preset, period_start, period_end)


@router.get("/api/admin/kpi/dashboard/vc", response_model=DashboardResponse)
async def dashboard_vc(
    period: Period = Depends(_period_dep),
    _user: User = Depends(require_role("vc", "admin")),
    db: AsyncSession = Depends(get_session),
) -> DashboardResponse:
    return await _dashboard(db, "vc", VC_CODES, period)


@router.get("/api/admin/kpi/dashboard/dean", response_model=DashboardResponse)
async def dashboard_dean(
    period: Period = Depends(_period_dep),
    _user: User = Depends(require_role("manager", "vc", "admin")),
    db: AsyncSession = Depends(get_session),
) -> DashboardResponse:
    return await _dashboard(db, "dean", DEAN_CODES, period)


@router.get("/api/admin/kpi/dashboard/section-head", response_model=DashboardResponse)
async def dashboard_section_head(
    period: Period = Depends(_period_dep),
    _user: User = Depends(require_role("manager", "admin")),
    db: AsyncSession = Depends(get_session),
) -> DashboardResponse:
    return await _dashboard(db, "section-head", SECTION_HEAD_CODES, period)


@router.get("/api/admin/kpi/dashboard/finance", response_model=DashboardResponse)
async def dashboard_finance(
    period: Period = Depends(_period_dep),
    _user: User = Depends(require_role("finance", "admin")),
    db: AsyncSession = Depends(get_session),
) -> DashboardResponse:
    return await _dashboard(db, "finance", FINANCE_CODES, period)


@router.get("/api/admin/kpi/dashboard/me", response_model=DashboardResponse)
async def dashboard_me(
    period: Period = Depends(_period_dep),
    user: User = Depends(
        require_role("staff", "manager", "finance", "admin", "vc", "lecturer")
    ),
    db: AsyncSession = Depends(get_session),
) -> DashboardResponse:
    cards = await _build_cards(db, period, ME_CODES)
    assigned = await db.scalar(
        select(func.count())
        .select_from(Enquiry)
        .where(
            Enquiry.assigned_staff_id == user.id,
            Enquiry.resolved_at.is_not(None),
            Enquiry.resolved_at >= period.start_dt,
            Enquiry.resolved_at <= period.end_dt,
        )
    ) or 0
    cards.append(
        DashboardCard(
            code="me.enquiries_resolved",
            name="Enquiries You Resolved",
            category="individual",
            unit="count",
            direction="higher_better",
            value=float(assigned),
            target=None,
            status="grey",
        )
    )
    return DashboardResponse(
        view="me",
        period_start=period.start,
        period_end=period.end,
        generated_at=datetime.now(UTC),
        cards=cards,
    )


# --- Finance CSV export ---------------------------------------------------


@router.get("/api/admin/kpi/dashboard/finance/export")
async def export_finance_csv(
    request: Request,
    period: Period = Depends(_period_dep),
    user: User = Depends(require_role("finance", "admin")),
    db: AsyncSession = Depends(get_session),
) -> Response:
    cards = await _build_cards(db, period, FINANCE_CODES)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["kpi_code", "name", "unit", "value", "target", "status"])
    for c in cards:
        writer.writerow(
            [c.code, c.name, c.unit, c.value, c.target if c.target is not None else "", c.status]
        )

    await write_audit_log(
        actor_user_id=user.id,
        action="kpi.finance.export",
        target_type="kpi_run",
        target_id=f"{period.start}:{period.end}",
        after={"period_start": str(period.start), "period_end": str(period.end), "format": "csv"},
        ip_address=request.client.host if request.client else None,
    )

    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={
            "Content-Disposition": (
                f'attachment; filename="finance_kpi_{period.start}_{period.end}.csv"'
            )
        },
    )
