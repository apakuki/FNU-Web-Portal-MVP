"""Mock Banner adapter for local development and tests.

Returns seeded data matching real FNU programme/course structures.
Never use in production — factory.py validates this at startup.
"""

from datetime import date

from src.backend.banner.base import BannerClient
from src.backend.banner.types import (
    BannerHealthResponse,
    BannerStudent,
    Campus,
    ClassRoster,
    Course,
    CreateInvoiceRequest,
    CreateInvoiceResponse,
    CreateStudentRequest,
    CreateStudentResponse,
    FeeItem,
    FeeSchedule,
    Invoice,
    Offering,
    Prerequisite,
    Programme,
    RegisterCourseRequest,
    RegisterCourseResponse,
    RosterEntry,
    Semester,
    SubmitGradeRequest,
    SubmitGradeResponse,
)

PROGRAMMES: list[Programme] = [
    Programme(
        code="BCOM",
        name="Bachelor of Commerce",
        level="Degree",
        college="CBHTS",
        campus_codes=["Nasinu", "Lautoka"],
        duration_years=3,
        total_credits=360,
    ),
    Programme(
        code="BSCI",
        name="Bachelor of Science",
        level="Degree",
        college="CEST",
        campus_codes=["Nasinu"],
        duration_years=3,
        total_credits=360,
    ),
    Programme(
        code="BNUR",
        name="Bachelor of Nursing",
        level="Degree",
        college="CMNHS",
        campus_codes=["Suva", "Lautoka"],
        duration_years=4,
        total_credits=480,
    ),
    Programme(
        code="DIT",
        name="Diploma in Information Technology",
        level="Diploma",
        college="CEST",
        campus_codes=["Nasinu", "Labasa"],
        duration_years=2,
        total_credits=240,
    ),
    Programme(
        code="CEDU",
        name="Certificate in Education",
        level="Certificate",
        college="CBHTS",
        campus_codes=["Nasinu", "Lautoka", "Labasa"],
        duration_years=1,
        total_credits=120,
    ),
]

COURSES: list[Course] = [
    Course(
        code="ACC101",
        name="Introduction to Accounting",
        credits=15,
        programme_codes=["BCOM"],
        year_level=1,
        semester=Semester.S1,
    ),
    Course(
        code="ACC201",
        name="Intermediate Accounting",
        credits=15,
        programme_codes=["BCOM"],
        year_level=2,
        semester=Semester.S1,
        prerequisites=[Prerequisite(course_code="ACC101", min_grade="C")],
    ),
    Course(
        code="MGT101",
        name="Principles of Management",
        credits=15,
        programme_codes=["BCOM"],
        year_level=1,
        semester=Semester.S1,
    ),
    Course(
        code="ECN101",
        name="Microeconomics",
        credits=15,
        programme_codes=["BCOM"],
        year_level=1,
        semester=Semester.S2,
    ),
    Course(
        code="BIO101",
        name="General Biology",
        credits=15,
        programme_codes=["BSCI", "BNUR"],
        year_level=1,
        semester=Semester.S1,
    ),
    Course(
        code="CHM101",
        name="General Chemistry",
        credits=15,
        programme_codes=["BSCI"],
        year_level=1,
        semester=Semester.S1,
    ),
    Course(
        code="PHY101",
        name="Physics I",
        credits=15,
        programme_codes=["BSCI"],
        year_level=1,
        semester=Semester.S2,
    ),
    Course(
        code="NUR101",
        name="Foundations of Nursing",
        credits=15,
        programme_codes=["BNUR"],
        year_level=1,
        semester=Semester.S1,
    ),
    Course(
        code="NUR201",
        name="Medical-Surgical Nursing",
        credits=15,
        programme_codes=["BNUR"],
        year_level=2,
        semester=Semester.S1,
        prerequisites=[Prerequisite(course_code="NUR101", min_grade="C")],
    ),
    Course(
        code="IT101",
        name="Introduction to Computing",
        credits=15,
        programme_codes=["DIT"],
        year_level=1,
        semester=Semester.S1,
    ),
    Course(
        code="IT102",
        name="Programming Fundamentals",
        credits=15,
        programme_codes=["DIT"],
        year_level=1,
        semester=Semester.S1,
    ),
    Course(
        code="EDU101",
        name="Foundations of Education",
        credits=15,
        programme_codes=["CEDU"],
        year_level=1,
        semester=Semester.S1,
    ),
]

OFFERINGS: list[Offering] = [
    Offering(
        id="OFF-2026-S1-ACC101-NAS",
        course_code="ACC101",
        semester=Semester.S1,
        year=2026,
        campus=Campus.NASINU,
        lecturer_name="Dr. Mere Tuisawau",
        lecturer_banner_id="L00010001",
        day_of_week="Monday",
        start_time="09:00",
        end_time="11:00",
        room="CBHTS-LT1",
        capacity=60,
        enrolled=42,
    ),
    Offering(
        id="OFF-2026-S1-MGT101-NAS",
        course_code="MGT101",
        semester=Semester.S1,
        year=2026,
        campus=Campus.NASINU,
        lecturer_name="Prof. Josefa Rakesa",
        lecturer_banner_id="L00010002",
        day_of_week="Tuesday",
        start_time="13:00",
        end_time="15:00",
        room="CBHTS-LT2",
        capacity=80,
        enrolled=65,
    ),
    Offering(
        id="OFF-2026-S1-BIO101-NAS",
        course_code="BIO101",
        semester=Semester.S1,
        year=2026,
        campus=Campus.NASINU,
        lecturer_name="Dr. Alumita Waqa",
        lecturer_banner_id="L00010003",
        day_of_week="Wednesday",
        start_time="10:00",
        end_time="12:00",
        room="CEST-SCI-201",
        capacity=40,
        enrolled=38,
    ),
    Offering(
        id="OFF-2026-S1-NUR101-SUV",
        course_code="NUR101",
        semester=Semester.S1,
        year=2026,
        campus=Campus.SUVA,
        lecturer_name="Sister Vasiti Naidu",
        lecturer_banner_id="L00010004",
        day_of_week="Thursday",
        start_time="08:00",
        end_time="10:00",
        room="CMNHS-CL3",
        capacity=30,
        enrolled=28,
    ),
    Offering(
        id="OFF-2026-S1-IT101-NAS",
        course_code="IT101",
        semester=Semester.S1,
        year=2026,
        campus=Campus.NASINU,
        lecturer_name="Mr. Vikash Sharma",
        lecturer_banner_id="L00010005",
        day_of_week="Friday",
        start_time="09:00",
        end_time="11:00",
        room="CEST-LAB-1",
        capacity=35,
        enrolled=30,
    ),
]

STUDENTS: list[BannerStudent] = [
    BannerStudent(
        banner_id="S00012345",
        first_name="Apisai",
        last_name="Delana",
        email="student@fnu.ac.fj",
        phone="+6799991001",
        programme_code="BCOM",
        campus=Campus.NASINU,
        enrolment_status="active",
        gpa=3.2,
    ),
    BannerStudent(
        banner_id="S00012346",
        first_name="Litia",
        last_name="Nabalarua",
        email="student2@fnu.ac.fj",
        phone="+6799991002",
        programme_code="BNUR",
        campus=Campus.SUVA,
        enrolment_status="active",
        gpa=3.7,
    ),
]

FEE_ITEMS_2026_S1: list[FeeItem] = [
    FeeItem(
        code="TUI-BCOM",
        description="Tuition Fee — Bachelor of Commerce",
        amount_cents=350000,
        applies_to="BCOM",
        fee_type="tuition",
    ),
    FeeItem(
        code="TUI-BSCI",
        description="Tuition Fee — Bachelor of Science",
        amount_cents=400000,
        applies_to="BSCI",
        fee_type="tuition",
    ),
    FeeItem(
        code="TUI-BNUR",
        description="Tuition Fee — Bachelor of Nursing",
        amount_cents=380000,
        applies_to="BNUR",
        fee_type="tuition",
    ),
    FeeItem(
        code="TUI-DIT",
        description="Tuition Fee — Diploma in IT",
        amount_cents=250000,
        applies_to="DIT",
        fee_type="tuition",
    ),
    FeeItem(
        code="TUI-CEDU",
        description="Tuition Fee — Certificate in Education",
        amount_cents=180000,
        applies_to="CEDU",
        fee_type="tuition",
    ),
    FeeItem(
        code="REG-ALL",
        description="Registration Fee",
        amount_cents=15000,
        applies_to="ALL",
        fee_type="registration",
    ),
    FeeItem(
        code="LIB-ALL",
        description="Library Fee",
        amount_cents=5000,
        applies_to="ALL",
        fee_type="library",
    ),
    FeeItem(
        code="LAB-SCI",
        description="Science Laboratory Fee",
        amount_cents=12000,
        applies_to="BSCI",
        fee_type="lab",
    ),
    FeeItem(
        code="LAB-NUR",
        description="Nursing Lab Fee",
        amount_cents=15000,
        applies_to="BNUR",
        fee_type="lab",
    ),
    FeeItem(
        code="EXM-ALL",
        description="Examination Fee",
        amount_cents=8000,
        applies_to="ALL",
        fee_type="exam",
    ),
]

INVOICES: list[Invoice] = [
    Invoice(
        invoice_id="INV-2026-S1-00001",
        banner_student_id="S00012345",
        semester=Semester.S1,
        year=2026,
        items=[
            FeeItem(
                code="TUI-BCOM",
                description="Tuition Fee — Bachelor of Commerce",
                amount_cents=350000,
                applies_to="BCOM",
                fee_type="tuition",
            ),
            FeeItem(
                code="REG-ALL",
                description="Registration Fee",
                amount_cents=15000,
                applies_to="ALL",
                fee_type="registration",
            ),
            FeeItem(
                code="LIB-ALL",
                description="Library Fee",
                amount_cents=5000,
                applies_to="ALL",
                fee_type="library",
            ),
            FeeItem(
                code="EXM-ALL",
                description="Examination Fee",
                amount_cents=8000,
                applies_to="ALL",
                fee_type="exam",
            ),
        ],
        total_cents=378000,
        paid_cents=100000,
        due_date=date(2026, 3, 15),
        status="partial",
    ),
    Invoice(
        invoice_id="INV-2026-S1-00002",
        banner_student_id="S00012346",
        semester=Semester.S1,
        year=2026,
        items=[
            FeeItem(
                code="TUI-BNUR",
                description="Tuition Fee — Bachelor of Nursing",
                amount_cents=380000,
                applies_to="BNUR",
                fee_type="tuition",
            ),
            FeeItem(
                code="REG-ALL",
                description="Registration Fee",
                amount_cents=15000,
                applies_to="ALL",
                fee_type="registration",
            ),
            FeeItem(
                code="LAB-NUR",
                description="Nursing Lab Fee",
                amount_cents=15000,
                applies_to="BNUR",
                fee_type="lab",
            ),
        ],
        total_cents=410000,
        paid_cents=410000,
        due_date=date(2026, 3, 15),
        status="paid",
    ),
]


class MockBannerClient(BannerClient):
    """In-memory mock of Ellucian Banner for development and testing."""

    def __init__(self) -> None:
        self._next_student_seq = 12347
        self._next_invoice_seq = 3
        self._extra_students: list[BannerStudent] = []
        self._extra_invoices: list[Invoice] = []
        self._registrations: list[dict[str, str]] = []
        self._grades: list[dict[str, str]] = []

    async def get_programmes(self) -> list[Programme]:
        return [p for p in PROGRAMMES if p.code != "Dית"]

    async def get_courses(self, programme_code: str | None = None) -> list[Course]:
        if programme_code:
            return [c for c in COURSES if programme_code in c.programme_codes]
        return list(COURSES)

    async def get_offerings(
        self,
        course_code: str | None = None,
        semester: str | None = None,
        year: int | None = None,
    ) -> list[Offering]:
        result = list(OFFERINGS)
        if course_code:
            result = [o for o in result if o.course_code == course_code]
        if semester:
            result = [o for o in result if o.semester.value == semester]
        if year:
            result = [o for o in result if o.year == year]
        return result

    async def get_fee_schedule(self, year: int, semester: str) -> FeeSchedule:
        sem = Semester(semester)
        if year == 2026 and sem == Semester.S1:
            return FeeSchedule(year=year, semester=sem, items=FEE_ITEMS_2026_S1)
        return FeeSchedule(year=year, semester=sem, items=[])

    async def get_student(self, banner_id: str) -> BannerStudent | None:
        for s in STUDENTS + self._extra_students:
            if s.banner_id == banner_id:
                return s
        return None

    async def get_invoices(self, banner_student_id: str) -> list[Invoice]:
        all_invoices = INVOICES + self._extra_invoices
        return [inv for inv in all_invoices if inv.banner_student_id == banner_student_id]

    async def get_class_roster(self, offering_id: str) -> ClassRoster | None:
        offering = None
        for o in OFFERINGS:
            if o.id == offering_id:
                offering = o
                break
        if not offering:
            return None

        course = None
        for c in COURSES:
            if c.code == offering.course_code:
                course = c
                break

        entries = [
            RosterEntry(
                banner_student_id="S00012345",
                student_name="Apisai Delana",
                email="student@fnu.ac.fj",
                grade=None,
                attendance_pct=92.5,
            ),
        ]

        return ClassRoster(
            offering_id=offering_id,
            course_code=offering.course_code,
            course_name=course.name if course else offering.course_code,
            semester=offering.semester,
            year=offering.year,
            campus=offering.campus,
            entries=entries,
        )

    async def create_student(self, req: CreateStudentRequest) -> CreateStudentResponse:
        banner_id = f"S{self._next_student_seq:08d}"
        self._next_student_seq += 1
        self._extra_students.append(
            BannerStudent(
                banner_id=banner_id,
                first_name=req.first_name,
                last_name=req.last_name,
                email=req.email,
                phone=req.phone,
                programme_code=req.programme_code,
                campus=req.campus,
            )
        )
        return CreateStudentResponse(banner_id=banner_id)

    async def register_course(self, req: RegisterCourseRequest) -> RegisterCourseResponse:
        student = await self.get_student(req.banner_student_id)
        if not student:
            return RegisterCourseResponse(success=False, message="Student not found")

        offering = None
        for o in OFFERINGS:
            if o.id == req.offering_id:
                offering = o
                break
        if not offering:
            return RegisterCourseResponse(success=False, message="Offering not found")

        if offering.enrolled >= offering.capacity:
            return RegisterCourseResponse(success=False, message="Class is full")

        self._registrations.append(
            {"banner_student_id": req.banner_student_id, "offering_id": req.offering_id}
        )
        return RegisterCourseResponse(success=True, message="Registered successfully")

    async def submit_grade(self, req: SubmitGradeRequest) -> SubmitGradeResponse:
        valid_grades = {"A+", "A", "A-", "B+", "B", "B-", "C+", "C", "C-", "D", "E", "F", "WD"}
        if req.grade not in valid_grades:
            return SubmitGradeResponse(success=False, message=f"Invalid grade: {req.grade}")
        self._grades.append(
            {
                "offering_id": req.offering_id,
                "banner_student_id": req.banner_student_id,
                "grade": req.grade,
            }
        )
        return SubmitGradeResponse(success=True, message="Grade submitted")

    async def create_invoice(self, req: CreateInvoiceRequest) -> CreateInvoiceResponse:
        invoice_id = f"INV-{req.year}-{req.semester.value}-{self._next_invoice_seq:05d}"
        self._next_invoice_seq += 1
        total = sum(item.amount_cents for item in req.items)
        self._extra_invoices.append(
            Invoice(
                invoice_id=invoice_id,
                banner_student_id=req.banner_student_id,
                semester=req.semester,
                year=req.year,
                items=req.items,
                total_cents=total,
            )
        )
        return CreateInvoiceResponse(invoice_id=invoice_id, total_cents=total)

    async def health(self) -> BannerHealthResponse:
        return BannerHealthResponse(status="ok", latency_ms=1.0)
