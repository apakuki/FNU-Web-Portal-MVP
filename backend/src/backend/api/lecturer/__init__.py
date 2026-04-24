"""Lecturer API — class rosters and grade entry (Part 13).

Lecturers see the courses they teach in the current semester, inspect
the roster per course, export rosters to CSV/PDF, and enter grades.
Grade entry uses a draft / submitted / finalised workflow: autosaved
drafts can be freely edited; submitting locks them for the lecturer
(admin override required to re-open); finalising writes through to
Banner via `banner_client.submit_grade` and exposes them on the
student-facing "My Grades" view.

Every state transition is audit-logged with the before/after grade
values. All endpoints are scoped to the authenticated lecturer's
`banner_id` (prevents IDOR — a lecturer cannot see a colleague's
roster or edit their grades).
"""

from __future__ import annotations

import csv
import html
import io
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.backend.auth import require_role
from src.backend.banner import get_banner_client
from src.backend.banner.types import SubmitGradeRequest
from src.backend.db.models import LecturerGrade, User
from src.backend.db.session import get_session
from src.backend.services.audit_service import write_audit_log

router = APIRouter(tags=["lecturer"])

DEFAULT_SEMESTER = "S1"
DEFAULT_YEAR = 2026
VALID_GRADES = {
    "A+", "A", "A-",
    "B+", "B", "B-",
    "C+", "C", "C-",
    "D", "E", "F", "WD",
}
VALID_STATUSES = {"draft", "submitted", "finalised"}
VALID_EXPORT_FORMATS = {"csv", "xlsx", "pdf"}


# --- Schemas ---------------------------------------------------------------


class LecturerCourseSummary(BaseModel):
    offering_id: str
    course_code: str
    course_name: str
    semester: str
    year: int
    campus: str
    day_of_week: str
    start_time: str
    end_time: str
    room: str
    enrolled: int
    student_count: int
    draft_count: int
    submitted_count: int
    finalised_count: int


class LecturerRostersResponse(BaseModel):
    semester: str
    year: int
    courses: list[LecturerCourseSummary]


class RosterGradeEntry(BaseModel):
    banner_student_id: str
    student_name: str
    email: str
    attendance_pct: float | None
    grade: str | None
    status: str
    submitted_at: datetime | None
    finalised_at: datetime | None
    updated_at: datetime | None


class LecturerRosterDetail(BaseModel):
    offering_id: str
    course_code: str
    course_name: str
    semester: str
    year: int
    campus: str
    lecturer_name: str | None
    room: str
    day_of_week: str
    start_time: str
    end_time: str
    entries: list[RosterGradeEntry]


class GradeUpsertItem(BaseModel):
    banner_student_id: str = Field(min_length=1, max_length=20)
    grade: str | None = Field(default=None, max_length=4)


class GradeUpsertRequest(BaseModel):
    offering_id: str = Field(min_length=1, max_length=64)
    assessment_period: str = Field(default="final", min_length=1, max_length=32)
    entries: list[GradeUpsertItem] = Field(min_length=1, max_length=500)


class GradeUpsertResponse(BaseModel):
    saved: int
    status: str = "draft"


class GradeTransitionResponse(BaseModel):
    offering_id: str
    status: str
    affected: int
    message: str


# --- Helpers ---------------------------------------------------------------


def _require_lecturer_banner_id(user: User) -> str:
    if not user.banner_id:
        raise HTTPException(
            status_code=400,
            detail="Lecturer account is missing a Banner ID",
        )
    return user.banner_id


def _validate_grade(value: str | None) -> str | None:
    if value is None or value == "":
        return None
    trimmed = value.strip().upper()
    if trimmed not in VALID_GRADES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid grade '{value}'. Allowed: {', '.join(sorted(VALID_GRADES))}",
        )
    return trimmed


async def _offering_taught_by(
    lecturer_banner_id: str,
    offering_id: str,
    semester: str = DEFAULT_SEMESTER,
    year: int = DEFAULT_YEAR,
):
    banner = get_banner_client()
    offerings = await banner.get_offerings(semester=semester, year=year)
    for o in offerings:
        if o.id == offering_id and o.lecturer_banner_id == lecturer_banner_id:
            return o
    return None


def _grade_rows_to_map(
    rows: list[LecturerGrade],
) -> dict[str, LecturerGrade]:
    return {r.banner_student_id: r for r in rows}


# --- Endpoints -------------------------------------------------------------


@router.get("/api/lecturer/rosters", response_model=LecturerRostersResponse)
async def list_rosters(
    semester: str = DEFAULT_SEMESTER,
    year: int = DEFAULT_YEAR,
    lecturer: User = Depends(require_role("lecturer")),
    db: AsyncSession = Depends(get_session),
) -> LecturerRostersResponse:
    banner_id = _require_lecturer_banner_id(lecturer)
    banner = get_banner_client()
    offerings = await banner.get_offerings(semester=semester, year=year)
    mine = [o for o in offerings if o.lecturer_banner_id == banner_id]
    if not mine:
        return LecturerRostersResponse(semester=semester, year=year, courses=[])

    courses = {c.code: c for c in await banner.get_courses()}

    grade_rows = (
        await db.scalars(
            select(LecturerGrade).where(
                LecturerGrade.offering_id.in_([o.id for o in mine])
            )
        )
    ).all()
    by_offering: dict[str, list[LecturerGrade]] = {}
    for g in grade_rows:
        by_offering.setdefault(g.offering_id, []).append(g)

    summaries: list[LecturerCourseSummary] = []
    for o in mine:
        roster = await banner.get_class_roster(o.id)
        student_count = len(roster.entries) if roster else 0
        rows = by_offering.get(o.id, [])
        draft = sum(1 for r in rows if r.status == "draft")
        submitted = sum(1 for r in rows if r.status == "submitted")
        finalised = sum(1 for r in rows if r.status == "finalised")
        summaries.append(
            LecturerCourseSummary(
                offering_id=o.id,
                course_code=o.course_code,
                course_name=(
                    courses[o.course_code].name
                    if o.course_code in courses
                    else o.course_code
                ),
                semester=o.semester.value,
                year=o.year,
                campus=o.campus.value,
                day_of_week=o.day_of_week,
                start_time=o.start_time,
                end_time=o.end_time,
                room=o.room,
                enrolled=o.enrolled,
                student_count=student_count,
                draft_count=draft,
                submitted_count=submitted,
                finalised_count=finalised,
            )
        )

    return LecturerRostersResponse(semester=semester, year=year, courses=summaries)


@router.get(
    "/api/lecturer/rosters/{offering_id}",
    response_model=LecturerRosterDetail,
)
async def get_roster_detail(
    offering_id: str,
    assessment_period: str = "final",
    lecturer: User = Depends(require_role("lecturer")),
    db: AsyncSession = Depends(get_session),
) -> LecturerRosterDetail:
    banner_id = _require_lecturer_banner_id(lecturer)
    offering = await _offering_taught_by(banner_id, offering_id)
    if not offering:
        raise HTTPException(status_code=404, detail="Offering not found or not taught by you")

    banner = get_banner_client()
    roster = await banner.get_class_roster(offering_id)
    if not roster:
        raise HTTPException(status_code=404, detail="Roster not available")

    grade_rows = (
        await db.scalars(
            select(LecturerGrade).where(
                and_(
                    LecturerGrade.offering_id == offering_id,
                    LecturerGrade.assessment_period == assessment_period,
                )
            )
        )
    ).all()
    by_student = _grade_rows_to_map(list(grade_rows))

    entries: list[RosterGradeEntry] = []
    for e in roster.entries:
        row = by_student.get(e.banner_student_id)
        entries.append(
            RosterGradeEntry(
                banner_student_id=e.banner_student_id,
                student_name=e.student_name,
                email=e.email,
                attendance_pct=e.attendance_pct,
                grade=row.grade if row else None,
                status=row.status if row else "draft",
                submitted_at=row.submitted_at if row else None,
                finalised_at=row.finalised_at if row else None,
                updated_at=row.updated_at if row else None,
            )
        )

    return LecturerRosterDetail(
        offering_id=offering_id,
        course_code=roster.course_code,
        course_name=roster.course_name,
        semester=roster.semester.value,
        year=roster.year,
        campus=roster.campus.value,
        lecturer_name=offering.lecturer_name,
        room=offering.room,
        day_of_week=offering.day_of_week,
        start_time=offering.start_time,
        end_time=offering.end_time,
        entries=entries,
    )


@router.get("/api/lecturer/rosters/{offering_id}/export")
async def export_roster(
    offering_id: str,
    format: str = Query("csv", pattern="^(csv|xlsx|pdf)$"),
    assessment_period: str = "final",
    lecturer: User = Depends(require_role("lecturer")),
    db: AsyncSession = Depends(get_session),
) -> Response:
    detail = await get_roster_detail(
        offering_id=offering_id,
        assessment_period=assessment_period,
        lecturer=lecturer,
        db=db,
    )

    filename_base = f"roster_{detail.course_code}_{detail.semester}_{detail.year}"

    if format in ("csv", "xlsx"):
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(
            [
                "banner_student_id",
                "student_name",
                "email",
                "attendance_pct",
                "grade",
                "status",
            ]
        )
        for e in detail.entries:
            writer.writerow(
                [
                    e.banner_student_id,
                    e.student_name,
                    e.email,
                    f"{e.attendance_pct:.1f}" if e.attendance_pct is not None else "",
                    e.grade or "",
                    e.status,
                ]
            )
        content = buf.getvalue().encode("utf-8")
        # Excel opens CSV files natively; we serve the same bytes with an .xlsx-friendly
        # MIME and filename when the client asks for 'xlsx' so the download feels native.
        if format == "xlsx":
            return Response(
                content=content,
                media_type="application/vnd.ms-excel",
                headers={
                    "Content-Disposition": f'attachment; filename="{filename_base}.csv"',
                },
            )
        return StreamingResponse(
            io.BytesIO(content),
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="{filename_base}.csv"',
            },
        )

    # pdf
    try:
        from weasyprint import HTML  # type: ignore[import-untyped]
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"PDF export unavailable: {exc}"
        ) from exc

    rows_html = "".join(
        "<tr>"
        f"<td>{html.escape(e.banner_student_id)}</td>"
        f"<td>{html.escape(e.student_name)}</td>"
        f"<td>{html.escape(e.email)}</td>"
        f"<td>{'' if e.attendance_pct is None else f'{e.attendance_pct:.1f}%'}</td>"
        f"<td>{html.escape(e.grade or '')}</td>"
        f"<td>{html.escape(e.status)}</td>"
        "</tr>"
        for e in detail.entries
    )
    doc = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Roster {html.escape(detail.course_code)}</title>
<style>
  body {{ font-family: Helvetica, Arial, sans-serif; color: #0A1F33; }}
  h1 {{ color: #003A70; margin-bottom: 4px; }}
  .meta {{ color: #6B7280; margin-bottom: 18px; font-size: 12px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
  th, td {{ border: 1px solid #D1D5DB; padding: 6px 8px; text-align: left; }}
  th {{ background: #F4F6F9; color: #003A70; }}
</style></head>
<body>
  <h1>Class Roster — {html.escape(detail.course_code)}</h1>
  <div class="meta">
    {html.escape(detail.course_name)} · {html.escape(detail.semester)} {detail.year} ·
    {html.escape(detail.campus)} · {html.escape(detail.day_of_week)}
    {html.escape(detail.start_time)}–{html.escape(detail.end_time)} ·
    Room {html.escape(detail.room)}
  </div>
  <table>
    <thead><tr>
      <th>Banner ID</th><th>Student</th><th>Email</th>
      <th>Attendance</th><th>Grade</th><th>Status</th>
    </tr></thead>
    <tbody>{rows_html}</tbody>
  </table>
</body></html>"""
    pdf_bytes = HTML(string=doc).write_pdf()
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename_base}.pdf"',
        },
    )


@router.post("/api/lecturer/grades", response_model=GradeUpsertResponse)
async def upsert_grade_drafts(
    body: GradeUpsertRequest,
    request: Request,
    lecturer: User = Depends(require_role("lecturer")),
    db: AsyncSession = Depends(get_session),
) -> GradeUpsertResponse:
    banner_id = _require_lecturer_banner_id(lecturer)
    offering = await _offering_taught_by(banner_id, body.offering_id)
    if not offering:
        raise HTTPException(status_code=404, detail="Offering not found or not taught by you")

    banner = get_banner_client()
    roster = await banner.get_class_roster(body.offering_id)
    valid_ids = (
        {e.banner_student_id for e in roster.entries} if roster else set()
    )

    grades_in: list[tuple[str, str | None]] = []
    for item in body.entries:
        if item.banner_student_id not in valid_ids:
            raise HTTPException(
                status_code=400,
                detail=f"{item.banner_student_id} is not on this roster",
            )
        grades_in.append((item.banner_student_id, _validate_grade(item.grade)))

    existing_rows = (
        await db.scalars(
            select(LecturerGrade).where(
                and_(
                    LecturerGrade.offering_id == body.offering_id,
                    LecturerGrade.assessment_period == body.assessment_period,
                    LecturerGrade.banner_student_id.in_(
                        [bid for bid, _ in grades_in]
                    ),
                )
            )
        )
    ).all()
    existing = {r.banner_student_id: r for r in existing_rows}

    saved = 0
    audit_payloads: list[dict] = []
    for bid, grade in grades_in:
        current = existing.get(bid)
        if current:
            if current.status == "finalised":
                raise HTTPException(
                    status_code=400,
                    detail=f"Grade for {bid} is finalised and cannot be edited",
                )
            if current.status == "submitted":
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Grade for {bid} has been submitted for review — "
                        "an admin must re-open before editing"
                    ),
                )
            before = current.grade
            current.grade = grade
            current.entered_by_user_id = lecturer.id
            saved += 1
            audit_payloads.append(
                {"banner_student_id": bid, "before": before, "after": grade}
            )
        else:
            row = LecturerGrade(
                offering_id=body.offering_id,
                course_code=offering.course_code,
                banner_student_id=bid,
                semester=offering.semester.value,
                year=offering.year,
                assessment_period=body.assessment_period,
                grade=grade,
                status="draft",
                entered_by_user_id=lecturer.id,
            )
            db.add(row)
            saved += 1
            audit_payloads.append(
                {"banner_student_id": bid, "before": None, "after": grade}
            )

    await db.commit()

    await write_audit_log(
        actor_user_id=lecturer.id,
        action="lecturer.grade.draft",
        target_type="offering",
        target_id=body.offering_id,
        after={
            "assessment_period": body.assessment_period,
            "changes": audit_payloads,
        },
        ip_address=request.client.host if request.client else None,
    )

    return GradeUpsertResponse(saved=saved, status="draft")


@router.post(
    "/api/lecturer/grades/{offering_id}/submit",
    response_model=GradeTransitionResponse,
)
async def submit_offering_grades(
    offering_id: str,
    request: Request,
    assessment_period: str = "final",
    lecturer: User = Depends(require_role("lecturer")),
    db: AsyncSession = Depends(get_session),
) -> GradeTransitionResponse:
    banner_id = _require_lecturer_banner_id(lecturer)
    offering = await _offering_taught_by(banner_id, offering_id)
    if not offering:
        raise HTTPException(status_code=404, detail="Offering not found or not taught by you")

    rows = (
        await db.scalars(
            select(LecturerGrade).where(
                and_(
                    LecturerGrade.offering_id == offering_id,
                    LecturerGrade.assessment_period == assessment_period,
                    LecturerGrade.status == "draft",
                )
            )
        )
    ).all()
    if not rows:
        raise HTTPException(status_code=400, detail="No draft grades to submit")

    missing = [r.banner_student_id for r in rows if not r.grade]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=(
                "All draft entries must have a grade before submitting. "
                f"Missing: {', '.join(sorted(missing))}"
            ),
        )

    now = datetime.now(UTC)
    for r in rows:
        r.status = "submitted"
        r.submitted_at = now
    await db.commit()

    await write_audit_log(
        actor_user_id=lecturer.id,
        action="lecturer.grade.submit",
        target_type="offering",
        target_id=offering_id,
        after={
            "assessment_period": assessment_period,
            "student_count": len(rows),
            "submitted_at": now.isoformat(),
        },
        ip_address=request.client.host if request.client else None,
    )

    return GradeTransitionResponse(
        offering_id=offering_id,
        status="submitted",
        affected=len(rows),
        message=f"Submitted {len(rows)} grades for review",
    )


@router.post(
    "/api/lecturer/grades/{offering_id}/finalise",
    response_model=GradeTransitionResponse,
)
async def finalise_offering_grades(
    offering_id: str,
    request: Request,
    assessment_period: str = "final",
    lecturer: User = Depends(require_role("lecturer")),
    db: AsyncSession = Depends(get_session),
) -> GradeTransitionResponse:
    banner_id = _require_lecturer_banner_id(lecturer)
    offering = await _offering_taught_by(banner_id, offering_id)
    if not offering:
        raise HTTPException(status_code=404, detail="Offering not found or not taught by you")

    rows = (
        await db.scalars(
            select(LecturerGrade).where(
                and_(
                    LecturerGrade.offering_id == offering_id,
                    LecturerGrade.assessment_period == assessment_period,
                    LecturerGrade.status == "submitted",
                )
            )
        )
    ).all()
    if not rows:
        raise HTTPException(
            status_code=400,
            detail="No submitted grades ready to finalise",
        )

    banner = get_banner_client()
    banner_failures: list[str] = []
    for r in rows:
        if not r.grade:
            banner_failures.append(f"{r.banner_student_id}: missing grade")
            continue
        result = await banner.submit_grade(
            SubmitGradeRequest(
                offering_id=offering_id,
                banner_student_id=r.banner_student_id,
                grade=r.grade,
            )
        )
        if not result.success:
            banner_failures.append(f"{r.banner_student_id}: {result.message}")

    if banner_failures:
        raise HTTPException(
            status_code=502,
            detail=(
                "Banner rejected one or more grade submissions. "
                + "; ".join(banner_failures)
            ),
        )

    now = datetime.now(UTC)
    for r in rows:
        r.status = "finalised"
        r.finalised_at = now
    await db.commit()

    await write_audit_log(
        actor_user_id=lecturer.id,
        action="lecturer.grade.finalise",
        target_type="offering",
        target_id=offering_id,
        after={
            "assessment_period": assessment_period,
            "student_count": len(rows),
            "finalised_at": now.isoformat(),
            "grades": [
                {"banner_student_id": r.banner_student_id, "grade": r.grade}
                for r in rows
            ],
        },
        ip_address=request.client.host if request.client else None,
    )

    return GradeTransitionResponse(
        offering_id=offering_id,
        status="finalised",
        affected=len(rows),
        message=f"Finalised {len(rows)} grades and wrote to Banner",
    )


@router.get(
    "/api/lecturer/grades/{offering_id}",
    response_model=list[RosterGradeEntry],
)
async def list_grade_entries(
    offering_id: str,
    assessment_period: str = "final",
    lecturer: User = Depends(require_role("lecturer")),
    db: AsyncSession = Depends(get_session),
) -> list[RosterGradeEntry]:
    detail = await get_roster_detail(
        offering_id=offering_id,
        assessment_period=assessment_period,
        lecturer=lecturer,
        db=db,
    )
    return detail.entries
