"""Course registration, timetable, grades, my-courses, and invoices API.

All student-facing endpoints are scoped to the authenticated user's banner_id.
"""

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from src.backend.auth import require_role
from src.backend.banner import get_banner_client
from src.backend.banner.types import CompletedCourse, FeeItem, Offering
from src.backend.db.models import User
from src.backend.rate_limit import limiter

router = APIRouter(tags=["registration"])

GRADE_ORDER: dict[str, int] = {
    "A+": 12, "A": 11, "A-": 10,
    "B+": 9, "B": 8, "B-": 7,
    "C+": 6, "C": 5, "C-": 4,
    "D": 3, "E": 2, "F": 1, "WD": 0,
}

GPA_POINTS: dict[str, float | None] = {
    "A+": 4.0, "A": 4.0, "A-": 3.7,
    "B+": 3.3, "B": 3.0, "B-": 2.7,
    "C+": 2.3, "C": 2.0, "C-": 1.7,
    "D": 1.0, "E": 0.5, "F": 0.0, "WD": None,
}

COURSES_PER_SEMESTER = 4
SEMESTER_START_DATES: dict[str, date] = {
    "2026-S1": date(2026, 2, 9),
    "2026-S2": date(2026, 7, 20),
}
SEMESTER_WEEKS = 14
DAY_OFFSETS = {
    "Monday": 0, "Tuesday": 1, "Wednesday": 2,
    "Thursday": 3, "Friday": 4, "Saturday": 5,
}


# ---------- Prereq validator ----------

def check_prerequisites(
    course_code: str,
    prerequisites: list[dict],
    completed: list[CompletedCourse],
) -> tuple[bool, list[str]]:
    if not prerequisites:
        return True, []
    completed_map = {c.course_code: c.grade for c in completed}
    issues: list[str] = []
    for prereq in prerequisites:
        req_code = prereq["course_code"]
        min_grade = prereq.get("min_grade")
        if req_code not in completed_map:
            issues.append(f"{req_code} not completed")
            continue
        if min_grade:
            student_grade = completed_map[req_code]
            if GRADE_ORDER.get(student_grade, 0) < GRADE_ORDER.get(min_grade, 0):
                issues.append(
                    f"{req_code}: grade {student_grade} below required {min_grade}"
                )
    return len(issues) == 0, issues


# ---------- Clash detector ----------

def _time_to_minutes(t: str) -> int:
    h, m = t.split(":")
    return int(h) * 60 + int(m)


def detect_clashes(offerings: list[Offering]) -> list[dict]:
    clashes: list[dict] = []
    for i, a in enumerate(offerings):
        for b in offerings[i + 1:]:
            if a.day_of_week != b.day_of_week:
                continue
            a_start = _time_to_minutes(a.start_time)
            a_end = _time_to_minutes(a.end_time)
            b_start = _time_to_minutes(b.start_time)
            b_end = _time_to_minutes(b.end_time)
            if a_start < b_end and b_start < a_end:
                overlap_start = max(a_start, b_start)
                overlap_end = min(a_end, b_end)
                clashes.append({
                    "offering_id_1": a.id,
                    "offering_id_2": b.id,
                    "course_1": a.course_code,
                    "course_2": b.course_code,
                    "day": a.day_of_week,
                    "overlap": (
                        f"{a.day_of_week} "
                        f"{overlap_start // 60:02d}:{overlap_start % 60:02d}-"
                        f"{overlap_end // 60:02d}:{overlap_end % 60:02d}"
                    ),
                })
    return clashes


# ---------- GPA calculator ----------

def calculate_gpa(courses: list[CompletedCourse]) -> float:
    total_points = 0.0
    total_credits = 0
    for c in courses:
        pts = GPA_POINTS.get(c.grade)
        if pts is None:
            continue
        total_points += pts * c.credits
        total_credits += c.credits
    if total_credits == 0:
        return 0.0
    return round(total_points / total_credits, 2)


def calculate_semester_gpas(
    courses: list[CompletedCourse],
) -> dict[str, float]:
    semesters: dict[str, list[CompletedCourse]] = {}
    for c in courses:
        key = f"{c.year}-{c.semester.value}"
        semesters.setdefault(key, []).append(c)
    return {k: calculate_gpa(v) for k, v in sorted(semesters.items())}


# ---------- Fee calculator ----------

def calculate_registration_fees(
    programme_code: str,
    num_courses: int,
    fee_items: list[FeeItem],
) -> list[FeeItem]:
    result: list[FeeItem] = []
    tuition_item = None
    for item in fee_items:
        if item.fee_type == "tuition" and (
            item.applies_to == programme_code or item.applies_to == "ALL"
        ):
            tuition_item = item
            break

    if tuition_item:
        per_course = tuition_item.amount_cents // COURSES_PER_SEMESTER
        result.append(FeeItem(
            code=f"{tuition_item.code}-PARTIAL",
            description=f"Tuition ({num_courses} courses)",
            amount_cents=per_course * num_courses,
            applies_to=programme_code,
            fee_type="tuition",
        ))

    for item in fee_items:
        if item.fee_type == "tuition":
            continue
        if item.applies_to == "ALL" or item.applies_to == programme_code:
            result.append(item)

    return result


# ---------- Helper ----------

def _require_banner_id(user: User) -> str:
    if not user.banner_id:
        raise HTTPException(status_code=400, detail="No Banner ID linked to your account")
    return user.banner_id


# ---------- Response models ----------

class OfferingOut(BaseModel):
    id: str
    course_code: str
    course_name: str
    credits: int
    day_of_week: str
    start_time: str
    end_time: str
    room: str
    campus: str
    lecturer_name: str | None
    capacity: int
    enrolled: int
    available: bool
    prereqs_met: bool
    prereq_issues: list[str]


class ProgrammeResponse(BaseModel):
    code: str
    name: str
    level: str
    college: str
    total_credits: int
    completed_credits: int
    courses: list[OfferingOut]


class RegistrationConfirmRequest(BaseModel):
    offering_ids: list[str] = Field(min_length=1, max_length=10)
    semester: str = "S1"
    year: int = 2026


class RegistrationConfirmResponse(BaseModel):
    success: bool
    registered_courses: list[str]
    invoice_id: str | None = None
    total_fee_cents: int = 0
    clashes: list[dict] = []
    message: str


class GradeEntry(BaseModel):
    course_code: str
    course_name: str
    credits: int
    grade: str
    grade_points: float | None
    semester: str
    year: int


class GradesResponse(BaseModel):
    grades: list[GradeEntry]
    cumulative_gpa: float
    semester_gpas: dict[str, float]


class TimetableEntry(BaseModel):
    offering_id: str
    course_code: str
    course_name: str
    day_of_week: str
    start_time: str
    end_time: str
    room: str
    campus: str
    lecturer_name: str | None


class RegisteredCourse(BaseModel):
    offering_id: str
    course_code: str
    course_name: str
    credits: int
    day_of_week: str
    start_time: str
    end_time: str
    room: str
    campus: str
    lecturer_name: str | None


class InvoiceItem(BaseModel):
    code: str
    description: str
    amount_cents: int
    fee_type: str


class InvoiceOut(BaseModel):
    invoice_id: str
    semester: str
    year: int
    items: list[InvoiceItem]
    total_cents: int
    paid_cents: int
    due_date: str | None
    status: str
    balance_cents: int


# ---------- Programme & available courses ----------

@router.get("/api/programme")
async def get_programme(
    user: User = Depends(require_role("student")),
):
    banner_id = _require_banner_id(user)
    banner = get_banner_client()
    student = await banner.get_student(banner_id)
    if not student or not student.programme_code:
        raise HTTPException(status_code=404, detail="Programme not found")

    programmes = await banner.get_programmes()
    programme = next((p for p in programmes if p.code == student.programme_code), None)
    if not programme:
        raise HTTPException(status_code=404, detail="Programme not found in Banner")

    courses = await banner.get_courses(student.programme_code)
    completed = await banner.get_completed_courses(banner_id)
    completed_codes = {c.course_code for c in completed}
    completed_credits = sum(c.credits for c in completed)

    offerings = await banner.get_offerings(semester="S1", year=2026)
    programme_offerings = [
        o for o in offerings
        if o.course_code in {c.code for c in courses}
        and o.course_code not in completed_codes
        and (student.campus is None or o.campus.value == student.campus.value)
    ]

    offering_list: list[OfferingOut] = []
    for o in programme_offerings:
        course = next((c for c in courses if c.code == o.course_code), None)
        if not course:
            continue
        prereqs_met, issues = check_prerequisites(
            o.course_code,
            [p.model_dump() for p in course.prerequisites],
            completed,
        )
        offering_list.append(OfferingOut(
            id=o.id,
            course_code=o.course_code,
            course_name=course.name,
            credits=course.credits,
            day_of_week=o.day_of_week,
            start_time=o.start_time,
            end_time=o.end_time,
            room=o.room,
            campus=o.campus.value,
            lecturer_name=o.lecturer_name,
            capacity=o.capacity,
            enrolled=o.enrolled,
            available=o.enrolled < o.capacity,
            prereqs_met=prereqs_met,
            prereq_issues=issues,
        ))

    return ProgrammeResponse(
        code=programme.code,
        name=programme.name,
        level=programme.level,
        college=programme.college,
        total_credits=programme.total_credits,
        completed_credits=completed_credits,
        courses=offering_list,
    )


# ---------- Registration confirm ----------

@router.post("/api/registration/confirm")
@limiter.limit("3/minute")
async def confirm_registration(
    request: Request,
    body: RegistrationConfirmRequest,
    user: User = Depends(require_role("student")),
):
    banner_id = _require_banner_id(user)
    banner = get_banner_client()
    student = await banner.get_student(banner_id)
    if not student or not student.programme_code:
        raise HTTPException(status_code=400, detail="Student record not found")

    all_offerings = await banner.get_offerings(
        semester=body.semester, year=body.year
    )
    selected: list[Offering] = []
    for oid in body.offering_ids:
        offering = next((o for o in all_offerings if o.id == oid), None)
        if not offering:
            raise HTTPException(status_code=400, detail=f"Offering {oid} not found")
        selected.append(offering)

    clashes = detect_clashes(selected)
    if clashes:
        return RegistrationConfirmResponse(
            success=False,
            registered_courses=[],
            clashes=clashes,
            message="Timetable clashes detected",
        )

    completed = await banner.get_completed_courses(banner_id)
    courses = await banner.get_courses(student.programme_code)
    course_map = {c.code: c for c in courses}

    for offering in selected:
        course = course_map.get(offering.course_code)
        if course and course.prerequisites:
            met, issues = check_prerequisites(
                offering.course_code,
                [p.model_dump() for p in course.prerequisites],
                completed,
            )
            if not met:
                raise HTTPException(
                    status_code=400,
                    detail=f"Prerequisites not met for {offering.course_code}: "
                    + "; ".join(issues),
                )

    from src.backend.banner.types import (
        CreateInvoiceRequest,
        RegisterCourseRequest,
        Semester,
    )

    registered: list[str] = []
    for offering in selected:
        result = await banner.register_course(
            RegisterCourseRequest(
                banner_student_id=banner_id,
                offering_id=offering.id,
            )
        )
        if not result.success:
            raise HTTPException(
                status_code=400,
                detail=f"Registration failed for {offering.course_code}: {result.message}",
            )
        registered.append(offering.course_code)

    fee_schedule = await banner.get_fee_schedule(body.year, body.semester)
    fee_items = calculate_registration_fees(
        student.programme_code, len(selected), fee_schedule.items
    )
    total = sum(item.amount_cents for item in fee_items)

    invoice_result = await banner.create_invoice(
        CreateInvoiceRequest(
            banner_student_id=banner_id,
            semester=Semester(body.semester),
            year=body.year,
            items=fee_items,
        )
    )

    return RegistrationConfirmResponse(
        success=True,
        registered_courses=registered,
        invoice_id=invoice_result.invoice_id,
        total_fee_cents=total,
        message=f"Registered for {len(registered)} courses. Invoice created.",
    )


# ---------- Timetable ----------

@router.get("/api/timetable")
async def get_timetable(
    user: User = Depends(require_role("student")),
) -> list[TimetableEntry]:
    banner_id = _require_banner_id(user)
    banner = get_banner_client()
    registrations = await banner.get_student_registrations(
        banner_id, semester="S1", year=2026
    )
    courses = await banner.get_courses()
    course_map = {c.code: c.name for c in courses}

    return [
        TimetableEntry(
            offering_id=o.id,
            course_code=o.course_code,
            course_name=course_map.get(o.course_code, o.course_code),
            day_of_week=o.day_of_week,
            start_time=o.start_time,
            end_time=o.end_time,
            room=o.room,
            campus=o.campus.value,
            lecturer_name=o.lecturer_name,
        )
        for o in registrations
    ]


@router.get("/api/timetable.ics")
async def get_timetable_ics(
    user: User = Depends(require_role("student")),
) -> PlainTextResponse:
    banner_id = _require_banner_id(user)
    banner = get_banner_client()
    registrations = await banner.get_student_registrations(
        banner_id, semester="S1", year=2026
    )
    courses = await banner.get_courses()
    course_map = {c.code: c.name for c in courses}

    sem_key = "2026-S1"
    sem_start = SEMESTER_START_DATES.get(sem_key, date(2026, 2, 9))

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//FNU//Student Portal//EN",
        "CALSCALE:GREGORIAN",
    ]

    for o in registrations:
        day_offset = DAY_OFFSETS.get(o.day_of_week, 0)
        first_day = sem_start + timedelta(days=day_offset)
        start_h, start_m = o.start_time.split(":")
        end_h, end_m = o.end_time.split(":")
        course_name = course_map.get(o.course_code, o.course_code)

        lines.extend([
            "BEGIN:VEVENT",
            f"DTSTART;TZID=Pacific/Fiji:{first_day.strftime('%Y%m%d')}"
            f"T{start_h}{start_m}00",
            f"DTEND;TZID=Pacific/Fiji:{first_day.strftime('%Y%m%d')}"
            f"T{end_h}{end_m}00",
            f"RRULE:FREQ=WEEKLY;COUNT={SEMESTER_WEEKS}",
            f"SUMMARY:{o.course_code} - {course_name}",
            f"LOCATION:{o.room}, {o.campus.value}",
            f"DESCRIPTION:Lecturer: {o.lecturer_name or 'TBA'}",
            "END:VEVENT",
        ])

    lines.append("END:VCALENDAR")

    return PlainTextResponse(
        content="\r\n".join(lines),
        media_type="text/calendar",
        headers={"Content-Disposition": "attachment; filename=timetable.ics"},
    )


# ---------- Grades ----------

@router.get("/api/grades")
async def get_grades(
    user: User = Depends(require_role("student")),
) -> GradesResponse:
    banner_id = _require_banner_id(user)
    banner = get_banner_client()
    completed = await banner.get_completed_courses(banner_id)

    grades = [
        GradeEntry(
            course_code=c.course_code,
            course_name=c.course_name,
            credits=c.credits,
            grade=c.grade,
            grade_points=GPA_POINTS.get(c.grade),
            semester=c.semester.value,
            year=c.year,
        )
        for c in completed
    ]

    return GradesResponse(
        grades=grades,
        cumulative_gpa=calculate_gpa(completed),
        semester_gpas=calculate_semester_gpas(completed),
    )


# ---------- My courses ----------

@router.get("/api/my-courses")
async def get_my_courses(
    user: User = Depends(require_role("student")),
) -> list[RegisteredCourse]:
    banner_id = _require_banner_id(user)
    banner = get_banner_client()
    registrations = await banner.get_student_registrations(
        banner_id, semester="S1", year=2026
    )
    courses = await banner.get_courses()
    course_map = {c.code: c for c in courses}

    return [
        RegisteredCourse(
            offering_id=o.id,
            course_code=o.course_code,
            course_name=course_map[o.course_code].name
            if o.course_code in course_map
            else o.course_code,
            credits=course_map[o.course_code].credits
            if o.course_code in course_map
            else 15,
            day_of_week=o.day_of_week,
            start_time=o.start_time,
            end_time=o.end_time,
            room=o.room,
            campus=o.campus.value,
            lecturer_name=o.lecturer_name,
        )
        for o in registrations
    ]


# ---------- Invoices ----------

@router.get("/api/invoices")
async def get_invoices(
    user: User = Depends(require_role("student")),
) -> list[InvoiceOut]:
    banner_id = _require_banner_id(user)
    banner = get_banner_client()
    invoices = await banner.get_invoices(banner_id)

    return [
        InvoiceOut(
            invoice_id=inv.invoice_id,
            semester=inv.semester.value,
            year=inv.year,
            items=[
                InvoiceItem(
                    code=item.code,
                    description=item.description,
                    amount_cents=item.amount_cents,
                    fee_type=item.fee_type,
                )
                for item in inv.items
            ],
            total_cents=inv.total_cents,
            paid_cents=inv.paid_cents,
            due_date=inv.due_date.isoformat() if inv.due_date else None,
            status=inv.status,
            balance_cents=inv.total_cents - inv.paid_cents,
        )
        for inv in invoices
    ]


@router.get("/api/invoices/{invoice_id}")
async def get_invoice_detail(
    invoice_id: str,
    user: User = Depends(require_role("student")),
) -> InvoiceOut:
    banner_id = _require_banner_id(user)
    banner = get_banner_client()
    invoices = await banner.get_invoices(banner_id)
    inv = next((i for i in invoices if i.invoice_id == invoice_id), None)
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")

    return InvoiceOut(
        invoice_id=inv.invoice_id,
        semester=inv.semester.value,
        year=inv.year,
        items=[
            InvoiceItem(
                code=item.code,
                description=item.description,
                amount_cents=item.amount_cents,
                fee_type=item.fee_type,
            )
            for item in inv.items
        ],
        total_cents=inv.total_cents,
        paid_cents=inv.paid_cents,
        due_date=inv.due_date.isoformat() if inv.due_date else None,
        status=inv.status,
        balance_cents=inv.total_cents - inv.paid_cents,
    )
