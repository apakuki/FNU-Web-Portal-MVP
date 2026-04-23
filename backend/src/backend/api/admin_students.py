"""Staff administration — student search, detail view, manual overrides (Part 12).

Staff and admins search the portal's student population, view a merged
record pulling data from the portal DB (user, profile, applications,
overrides) and Banner (programme, completed courses, registrations,
invoices), and apply manual overrides (prereq waiver, late registration,
overload) against a student. Every override requires a reason and is
captured in the audit log; the student is also notified.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.backend.auth import require_role
from src.backend.banner import get_banner_client
from src.backend.db.models import (
    Application,
    AuditLog,
    PaymentAttempt,
    StudentProfile,
    User,
)
from src.backend.db.session import get_session
from src.backend.services.notification_service import send_notification

router = APIRouter(tags=["admin-students"])

OVERRIDE_TYPES = {"prereq_waiver", "late_registration", "overload"}
REASON_MIN_LENGTH = 10


# --- Schemas ---------------------------------------------------------------


class StudentListItem(BaseModel):
    id: uuid.UUID
    banner_id: str | None
    email: str
    full_name: str
    phone: str | None
    is_active: bool
    programme_code: str | None = None
    campus: str | None = None
    enrolment_status: str | None = None


class StudentListResponse(BaseModel):
    items: list[StudentListItem]
    total: int
    page: int
    per_page: int


class StudentProfileOut(BaseModel):
    address_line1: str | None
    address_line2: str | None
    city: str | None
    country: str | None
    emergency_contact_name: str | None
    emergency_contact_phone: str | None
    emergency_contact_relationship: str | None


class StudentBannerOut(BaseModel):
    programme_code: str | None
    campus: str | None
    enrolment_status: str | None
    gpa: float | None


class CompletedCourseOut(BaseModel):
    course_code: str
    course_name: str
    grade: str
    credits: int
    semester: str
    year: int


class RegistrationOut(BaseModel):
    offering_id: str
    course_code: str
    day_of_week: str
    start_time: str
    end_time: str


class InvoiceSummary(BaseModel):
    invoice_id: str
    total_cents: int
    paid_cents: int
    balance_cents: int
    status: str


class PaymentSummary(BaseModel):
    id: uuid.UUID
    method: str
    amount_cents: int
    status: str
    created_at: datetime


class ApplicationSummary(BaseModel):
    id: uuid.UUID
    application_number: str
    status: str
    submitted_at: datetime
    decided_at: datetime | None


class OverrideRecord(BaseModel):
    id: int
    override_type: str
    reason: str
    subject: str | None
    actor_user_id: uuid.UUID | None
    applied_at: datetime


class StudentDetailResponse(BaseModel):
    id: uuid.UUID
    banner_id: str | None
    email: str
    full_name: str
    phone: str | None
    role: str
    is_active: bool
    created_at: datetime
    profile: StudentProfileOut | None
    banner: StudentBannerOut | None
    completed_courses: list[CompletedCourseOut]
    current_registrations: list[RegistrationOut]
    invoices: list[InvoiceSummary]
    recent_payments: list[PaymentSummary]
    applications: list[ApplicationSummary]
    overrides: list[OverrideRecord]


class OverrideRequest(BaseModel):
    override_type: str = Field(pattern=r"^(prereq_waiver|late_registration|overload)$")
    reason: str = Field(min_length=REASON_MIN_LENGTH, max_length=1000)
    subject: str | None = Field(
        default=None,
        max_length=80,
        description="Optional course code or offering id the override applies to",
    )


class OverrideResponse(BaseModel):
    id: int
    override_type: str
    reason: str
    subject: str | None
    applied_at: datetime


# --- Helpers ---------------------------------------------------------------


def _audit_to_override(row: AuditLog) -> OverrideRecord:
    payload = row.after or {}
    return OverrideRecord(
        id=row.id,
        override_type=payload.get("override_type", row.action.removeprefix("override.")),
        reason=row.reason or payload.get("reason", ""),
        subject=payload.get("subject"),
        actor_user_id=row.actor_user_id,
        applied_at=row.occurred_at,
    )


# --- Endpoints -------------------------------------------------------------


@router.get("/api/admin/students", response_model=StudentListResponse)
async def list_students(
    q: str | None = None,
    programme: str | None = None,
    campus: str | None = None,
    status: str | None = None,
    page: int = 1,
    per_page: int = 25,
    _user: User = Depends(require_role("staff", "admin")),
    db: AsyncSession = Depends(get_session),
) -> StudentListResponse:
    if page < 1 or per_page < 1 or per_page > 100:
        raise HTTPException(status_code=400, detail="Invalid pagination parameters")

    stmt = select(User).where(User.role == "student")
    count_stmt = select(func.count()).select_from(User).where(User.role == "student")

    if q:
        like = f"%{q.lower()}%"
        condition = or_(
            func.lower(User.email).like(like),
            func.lower(User.full_name).like(like),
            func.lower(func.coalesce(User.banner_id, "")).like(like),
        )
        stmt = stmt.where(condition)
        count_stmt = count_stmt.where(condition)

    total = await db.scalar(count_stmt) or 0

    rows = (
        await db.scalars(
            stmt.order_by(User.full_name).offset((page - 1) * per_page).limit(per_page)
        )
    ).all()

    banner = get_banner_client()
    items: list[StudentListItem] = []
    for u in rows:
        programme_code: str | None = None
        campus_code: str | None = None
        enrolment_status: str | None = None
        if u.banner_id:
            bs = await banner.get_student(u.banner_id)
            if bs:
                programme_code = bs.programme_code
                campus_code = bs.campus.value if bs.campus else None
                enrolment_status = bs.enrolment_status

        if programme and programme_code != programme:
            continue
        if campus and campus_code != campus:
            continue
        if status and enrolment_status != status:
            continue

        items.append(
            StudentListItem(
                id=u.id,
                banner_id=u.banner_id,
                email=u.email,
                full_name=u.full_name,
                phone=u.phone,
                is_active=u.is_active,
                programme_code=programme_code,
                campus=campus_code,
                enrolment_status=enrolment_status,
            )
        )

    return StudentListResponse(items=items, total=total, page=page, per_page=per_page)


@router.get(
    "/api/admin/students/{user_id}", response_model=StudentDetailResponse
)
async def get_student_detail(
    user_id: uuid.UUID,
    _user: User = Depends(require_role("staff", "admin")),
    db: AsyncSession = Depends(get_session),
) -> StudentDetailResponse:
    user = await db.scalar(select(User).where(User.id == user_id))
    if not user or user.role != "student":
        raise HTTPException(status_code=404, detail="Student not found")

    profile_row = await db.scalar(
        select(StudentProfile).where(StudentProfile.user_id == user_id)
    )
    profile_out: StudentProfileOut | None = None
    if profile_row:
        profile_out = StudentProfileOut(
            address_line1=profile_row.address_line1,
            address_line2=profile_row.address_line2,
            city=profile_row.city,
            country=profile_row.country,
            emergency_contact_name=profile_row.emergency_contact_name,
            emergency_contact_phone=profile_row.emergency_contact_phone,
            emergency_contact_relationship=profile_row.emergency_contact_relationship,
        )

    banner_out: StudentBannerOut | None = None
    completed_out: list[CompletedCourseOut] = []
    registrations_out: list[RegistrationOut] = []
    invoices_out: list[InvoiceSummary] = []

    if user.banner_id:
        banner = get_banner_client()
        bs = await banner.get_student(user.banner_id)
        if bs:
            banner_out = StudentBannerOut(
                programme_code=bs.programme_code,
                campus=bs.campus.value if bs.campus else None,
                enrolment_status=bs.enrolment_status,
                gpa=bs.gpa,
            )

        completed = await banner.get_completed_courses(user.banner_id)
        completed_out = [
            CompletedCourseOut(
                course_code=c.course_code,
                course_name=c.course_name,
                grade=c.grade,
                credits=c.credits,
                semester=c.semester.value,
                year=c.year,
            )
            for c in completed
        ]

        registrations = await banner.get_student_registrations(
            user.banner_id, semester="S1", year=2026
        )
        registrations_out = [
            RegistrationOut(
                offering_id=o.id,
                course_code=o.course_code,
                day_of_week=o.day_of_week,
                start_time=o.start_time,
                end_time=o.end_time,
            )
            for o in registrations
        ]

        invoices = await banner.get_invoices(user.banner_id)
        invoices_out = [
            InvoiceSummary(
                invoice_id=inv.invoice_id,
                total_cents=inv.total_cents,
                paid_cents=inv.paid_cents,
                balance_cents=inv.total_cents - inv.paid_cents,
                status=inv.status,
            )
            for inv in invoices
        ]

    payments = (
        await db.scalars(
            select(PaymentAttempt)
            .where(PaymentAttempt.user_id == user_id)
            .order_by(PaymentAttempt.created_at.desc())
            .limit(10)
        )
    ).all()
    payments_out = [
        PaymentSummary(
            id=p.id,
            method=p.method,
            amount_cents=p.amount_cents,
            status=p.status,
            created_at=p.created_at,
        )
        for p in payments
    ]

    application_rows = (
        await db.scalars(
            select(Application)
            .where(
                or_(
                    Application.linked_user_id == user_id,
                    Application.applicant_email == user.email,
                )
            )
            .order_by(Application.submitted_at.desc())
        )
    ).all()
    applications_out = [
        ApplicationSummary(
            id=a.id,
            application_number=a.application_number,
            status=a.status,
            submitted_at=a.submitted_at,
            decided_at=a.decided_at,
        )
        for a in application_rows
    ]

    override_rows = (
        await db.scalars(
            select(AuditLog)
            .where(
                AuditLog.target_type == "student_override",
                AuditLog.target_id == str(user_id),
            )
            .order_by(AuditLog.occurred_at.desc())
            .limit(50)
        )
    ).all()
    overrides_out = [_audit_to_override(r) for r in override_rows]

    return StudentDetailResponse(
        id=user.id,
        banner_id=user.banner_id,
        email=user.email,
        full_name=user.full_name,
        phone=user.phone,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
        profile=profile_out,
        banner=banner_out,
        completed_courses=completed_out,
        current_registrations=registrations_out,
        invoices=invoices_out,
        recent_payments=payments_out,
        applications=applications_out,
        overrides=overrides_out,
    )


@router.post(
    "/api/admin/students/{user_id}/overrides",
    response_model=OverrideResponse,
    status_code=201,
)
async def create_override(
    user_id: uuid.UUID,
    body: OverrideRequest,
    request: Request,
    admin: User = Depends(require_role("staff", "admin")),
    db: AsyncSession = Depends(get_session),
) -> OverrideResponse:
    if body.override_type not in OVERRIDE_TYPES:
        raise HTTPException(status_code=400, detail="Unknown override type")

    student = await db.scalar(select(User).where(User.id == user_id))
    if not student or student.role != "student":
        raise HTTPException(status_code=404, detail="Student not found")

    entry = AuditLog(
        actor_user_id=admin.id,
        action=f"override.{body.override_type}",
        target_type="student_override",
        target_id=str(user_id),
        before=None,
        after={
            "override_type": body.override_type,
            "subject": body.subject,
            "reason": body.reason,
            "student_email": student.email,
        },
        reason=body.reason,
        ip_address=request.client.host if request.client else None,
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)

    await send_notification(
        channel="email",
        recipient_user_id=student.id,
        recipient_email=student.email,
        subject=f"Manual override applied — {body.override_type.replace('_', ' ')}",
        body=(
            f"An administrator has applied a {body.override_type.replace('_', ' ')} "
            f"override to your record."
            + (f" Subject: {body.subject}." if body.subject else "")
            + f" Reason: {body.reason}"
        ),
    )

    return OverrideResponse(
        id=entry.id,
        override_type=body.override_type,
        reason=body.reason,
        subject=body.subject,
        applied_at=entry.occurred_at,
    )


@router.get(
    "/api/admin/students/{user_id}/overrides",
    response_model=list[OverrideRecord],
)
async def list_overrides(
    user_id: uuid.UUID,
    _user: User = Depends(require_role("staff", "admin")),
    db: AsyncSession = Depends(get_session),
) -> list[OverrideRecord]:
    rows = (
        await db.scalars(
            select(AuditLog)
            .where(
                AuditLog.target_type == "student_override",
                AuditLog.target_id == str(user_id),
            )
            .order_by(AuditLog.occurred_at.desc())
            .limit(100)
        )
    ).all()
    return [_audit_to_override(r) for r in rows]


# --- Admin dashboard summary ----------------------------------------------


class DashboardSummary(BaseModel):
    pending_applications: int
    applications_awaiting_documents: int
    open_enquiries: int
    escalated_enquiries: int
    avg_application_decision_hours: float | None
    avg_enquiry_resolution_hours: float | None
    active_students: int


@router.get("/api/admin/dashboard/summary", response_model=DashboardSummary)
async def dashboard_summary(
    _user: User = Depends(require_role("staff", "admin")),
    db: AsyncSession = Depends(get_session),
) -> DashboardSummary:
    from src.backend.db.models import Enquiry  # local import avoids cycles

    pending_apps = await db.scalar(
        select(func.count())
        .select_from(Application)
        .where(Application.status.in_(("submitted", "under_review")))
    ) or 0

    awaiting_docs = await db.scalar(
        select(func.count())
        .select_from(Application)
        .where(Application.status == "awaiting_documents")
    ) or 0

    open_enq = await db.scalar(
        select(func.count())
        .select_from(Enquiry)
        .where(Enquiry.status.in_(("open", "in_progress")))
    ) or 0

    escalated_enq = await db.scalar(
        select(func.count())
        .select_from(Enquiry)
        .where(Enquiry.status == "open", Enquiry.source == "chatbot")
    ) or 0

    app_avg_seconds = await db.scalar(
        select(
            func.avg(
                func.extract("epoch", Application.decided_at)
                - func.extract("epoch", Application.submitted_at)
            )
        ).where(Application.decided_at.is_not(None))
    )

    enq_avg_seconds = await db.scalar(
        select(
            func.avg(
                func.extract("epoch", Enquiry.resolved_at)
                - func.extract("epoch", Enquiry.opened_at)
            )
        ).where(Enquiry.resolved_at.is_not(None))
    )

    active_students = await db.scalar(
        select(func.count())
        .select_from(User)
        .where(User.role == "student", User.is_active.is_(True))
    ) or 0

    return DashboardSummary(
        pending_applications=pending_apps,
        applications_awaiting_documents=awaiting_docs,
        open_enquiries=open_enq,
        escalated_enquiries=escalated_enq,
        avg_application_decision_hours=(
            round(float(app_avg_seconds) / 3600, 2) if app_avg_seconds else None
        ),
        avg_enquiry_resolution_hours=(
            round(float(enq_avg_seconds) / 3600, 2) if enq_avg_seconds else None
        ),
        active_students=active_students,
    )
