"""Staff administration — enquiry management (Part 12).

The enquiries queue collects items that reach the registry team in two
main ways: (a) the chatbot escalates a conversation and writes a row
(Part 9), (b) staff log an enquiry on behalf of a student who contacts
them by phone or in person. This module lets staff list the queue,
assign enquiries, transition status, record a resolution note, and the
student can rate the outcome.

Once a resolution note is written it must NOT be editable — the
integrity of the audit trail depends on it. Subsequent status changes
can still be made but the note is locked.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.backend.auth import require_role
from src.backend.db.models import Enquiry, User
from src.backend.db.session import get_session
from src.backend.services.audit_service import write_audit_log

router = APIRouter(tags=["admin-enquiries"])

VALID_STATUSES = {"open", "in_progress", "resolved", "closed"}
VALID_SOURCES = {"chatbot", "phone", "email", "walk_in", "staff"}


# --- Schemas ---------------------------------------------------------------


class EnquiryListItem(BaseModel):
    id: uuid.UUID
    subject: str
    source: str
    status: str
    student_identifier: str | None
    student_user_id: uuid.UUID | None
    assigned_staff_id: uuid.UUID | None
    opened_at: datetime
    resolved_at: datetime | None


class EnquiryListResponse(BaseModel):
    items: list[EnquiryListItem]
    total: int
    page: int
    per_page: int


class EnquiryDetailResponse(BaseModel):
    id: uuid.UUID
    subject: str
    body: str
    source: str
    status: str
    student_identifier: str | None
    student_user_id: uuid.UUID | None
    assigned_staff_id: uuid.UUID | None
    assigned_staff_name: str | None = None
    resolution_note: str | None
    student_feedback: int | None
    opened_at: datetime
    resolved_at: datetime | None


class EnquiryCreateRequest(BaseModel):
    subject: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=8000)
    source: str = Field(default="staff", pattern=r"^(chatbot|phone|email|walk_in|staff)$")
    student_user_id: uuid.UUID | None = None
    student_identifier: str | None = Field(default=None, max_length=120)


class EnquiryUpdateRequest(BaseModel):
    status: str | None = Field(
        default=None,
        pattern=r"^(open|in_progress|resolved|closed)$",
    )
    assigned_staff_id: uuid.UUID | None = None
    resolution_note: str | None = Field(default=None, min_length=1, max_length=4000)


class FeedbackRequest(BaseModel):
    rating: int = Field(ge=1, le=5)


# --- Helpers ---------------------------------------------------------------


def _to_detail(row: Enquiry, assigned_name: str | None = None) -> EnquiryDetailResponse:
    return EnquiryDetailResponse(
        id=row.id,
        subject=row.subject,
        body=row.body,
        source=row.source,
        status=row.status,
        student_identifier=row.student_identifier,
        student_user_id=row.student_user_id,
        assigned_staff_id=row.assigned_staff_id,
        assigned_staff_name=assigned_name,
        resolution_note=row.resolution_note,
        student_feedback=row.student_feedback,
        opened_at=row.opened_at,
        resolved_at=row.resolved_at,
    )


# --- Endpoints -------------------------------------------------------------


@router.get("/api/admin/enquiries", response_model=EnquiryListResponse)
async def list_enquiries(
    status: str | None = None,
    source: str | None = None,
    assigned_staff_id: uuid.UUID | None = None,
    q: str | None = None,
    page: int = 1,
    per_page: int = 25,
    _user: User = Depends(require_role("staff", "admin")),
    db: AsyncSession = Depends(get_session),
) -> EnquiryListResponse:
    if page < 1 or per_page < 1 or per_page > 100:
        raise HTTPException(status_code=400, detail="Invalid pagination parameters")

    conditions = []
    if status:
        if status not in VALID_STATUSES:
            raise HTTPException(status_code=400, detail="Invalid status filter")
        conditions.append(Enquiry.status == status)
    if source:
        if source not in VALID_SOURCES:
            raise HTTPException(status_code=400, detail="Invalid source filter")
        conditions.append(Enquiry.source == source)
    if assigned_staff_id:
        conditions.append(Enquiry.assigned_staff_id == assigned_staff_id)
    if q:
        like = f"%{q.lower()}%"
        conditions.append(
            or_(
                func.lower(Enquiry.subject).like(like),
                func.lower(Enquiry.body).like(like),
                func.lower(func.coalesce(Enquiry.student_identifier, "")).like(like),
            )
        )

    base_stmt = select(Enquiry)
    count_stmt = select(func.count()).select_from(Enquiry)
    if conditions:
        base_stmt = base_stmt.where(and_(*conditions))
        count_stmt = count_stmt.where(and_(*conditions))

    total = await db.scalar(count_stmt) or 0
    rows = (
        await db.scalars(
            base_stmt.order_by(Enquiry.opened_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
    ).all()

    items = [
        EnquiryListItem(
            id=r.id,
            subject=r.subject,
            source=r.source,
            status=r.status,
            student_identifier=r.student_identifier,
            student_user_id=r.student_user_id,
            assigned_staff_id=r.assigned_staff_id,
            opened_at=r.opened_at,
            resolved_at=r.resolved_at,
        )
        for r in rows
    ]
    return EnquiryListResponse(items=items, total=total, page=page, per_page=per_page)


@router.get(
    "/api/admin/enquiries/{enquiry_id}", response_model=EnquiryDetailResponse
)
async def get_enquiry(
    enquiry_id: uuid.UUID,
    _user: User = Depends(require_role("staff", "admin")),
    db: AsyncSession = Depends(get_session),
) -> EnquiryDetailResponse:
    row = await db.scalar(select(Enquiry).where(Enquiry.id == enquiry_id))
    if not row:
        raise HTTPException(status_code=404, detail="Enquiry not found")

    assigned_name: str | None = None
    if row.assigned_staff_id:
        staff = await db.scalar(select(User).where(User.id == row.assigned_staff_id))
        assigned_name = staff.full_name if staff else None

    return _to_detail(row, assigned_name)


@router.post(
    "/api/admin/enquiries",
    response_model=EnquiryDetailResponse,
    status_code=201,
)
async def create_enquiry(
    body: EnquiryCreateRequest,
    request: Request,
    staff: User = Depends(require_role("staff", "admin")),
    db: AsyncSession = Depends(get_session),
) -> EnquiryDetailResponse:
    entry = Enquiry(
        source=body.source,
        subject=body.subject,
        body=body.body,
        student_user_id=body.student_user_id,
        student_identifier=body.student_identifier,
        status="open",
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)

    await write_audit_log(
        actor_user_id=staff.id,
        action="enquiry.create",
        target_type="enquiry",
        target_id=str(entry.id),
        after={
            "subject": entry.subject,
            "source": entry.source,
            "student_user_id": str(entry.student_user_id) if entry.student_user_id else None,
        },
        ip_address=request.client.host if request.client else None,
    )
    return _to_detail(entry)


@router.put(
    "/api/admin/enquiries/{enquiry_id}", response_model=EnquiryDetailResponse
)
async def update_enquiry(
    enquiry_id: uuid.UUID,
    body: EnquiryUpdateRequest,
    request: Request,
    staff: User = Depends(require_role("staff", "admin")),
    db: AsyncSession = Depends(get_session),
) -> EnquiryDetailResponse:
    row = await db.scalar(select(Enquiry).where(Enquiry.id == enquiry_id))
    if not row:
        raise HTTPException(status_code=404, detail="Enquiry not found")

    before = {
        "status": row.status,
        "assigned_staff_id": (
            str(row.assigned_staff_id) if row.assigned_staff_id else None
        ),
        "resolution_note_set": row.resolution_note is not None,
    }

    if body.resolution_note is not None:
        if row.resolution_note is not None:
            raise HTTPException(
                status_code=400,
                detail="Resolution note cannot be edited once written",
            )
        row.resolution_note = body.resolution_note

    if body.assigned_staff_id is not None:
        assignee = await db.scalar(
            select(User).where(User.id == body.assigned_staff_id)
        )
        if not assignee or assignee.role not in ("staff", "admin"):
            raise HTTPException(
                status_code=400, detail="Assignee must be a staff or admin user"
            )
        row.assigned_staff_id = body.assigned_staff_id

    if body.status is not None:
        if body.status not in VALID_STATUSES:
            raise HTTPException(status_code=400, detail="Invalid status")
        if body.status == "resolved" and row.resolution_note is None:
            raise HTTPException(
                status_code=400,
                detail="Resolution note is required before marking resolved",
            )
        row.status = body.status
        if body.status in ("resolved", "closed") and row.resolved_at is None:
            row.resolved_at = datetime.now(UTC)

    await db.commit()
    await db.refresh(row)

    await write_audit_log(
        actor_user_id=staff.id,
        action="enquiry.update",
        target_type="enquiry",
        target_id=str(row.id),
        before=before,
        after={
            "status": row.status,
            "assigned_staff_id": (
                str(row.assigned_staff_id) if row.assigned_staff_id else None
            ),
            "resolution_note_set": row.resolution_note is not None,
        },
        ip_address=request.client.host if request.client else None,
    )

    assigned_name: str | None = None
    if row.assigned_staff_id:
        staff_user = await db.scalar(
            select(User).where(User.id == row.assigned_staff_id)
        )
        assigned_name = staff_user.full_name if staff_user else None

    return _to_detail(row, assigned_name)


@router.post(
    "/api/admin/enquiries/{enquiry_id}/feedback",
    response_model=EnquiryDetailResponse,
)
async def submit_feedback(
    enquiry_id: uuid.UUID,
    body: FeedbackRequest,
    request: Request,
    staff: User = Depends(require_role("staff", "admin")),
    db: AsyncSession = Depends(get_session),
) -> EnquiryDetailResponse:
    row = await db.scalar(select(Enquiry).where(Enquiry.id == enquiry_id))
    if not row:
        raise HTTPException(status_code=404, detail="Enquiry not found")
    if row.status not in ("resolved", "closed"):
        raise HTTPException(
            status_code=400, detail="Feedback can only be recorded on a resolved enquiry"
        )
    if row.student_feedback is not None:
        raise HTTPException(
            status_code=400, detail="Feedback has already been recorded"
        )

    row.student_feedback = body.rating
    await db.commit()
    await db.refresh(row)

    await write_audit_log(
        actor_user_id=staff.id,
        action="enquiry.feedback",
        target_type="enquiry",
        target_id=str(row.id),
        after={"rating": body.rating},
        ip_address=request.client.host if request.client else None,
    )
    return _to_detail(row)
