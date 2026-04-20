from datetime import date
from enum import StrEnum

from pydantic import BaseModel, Field


class Campus(StrEnum):
    NASINU = "Nasinu"
    LAUTOKA = "Lautoka"
    LABASA = "Labasa"
    NAUSORI = "Nausori"
    BA = "Ba"
    SUVA = "Suva"


class Semester(StrEnum):
    S1 = "S1"
    S2 = "S2"
    SUMMER = "Summer"


class Programme(BaseModel):
    code: str = Field(description="e.g. BCOM, BSCI")
    name: str
    level: str = Field(description="e.g. Certificate, Diploma, Degree, Postgrad")
    college: str = Field(description="e.g. CBHTS, CEST, CMNHS")
    campus_codes: list[str]
    duration_years: int
    total_credits: int
    is_active: bool = True


class Prerequisite(BaseModel):
    course_code: str
    min_grade: str | None = None


class Course(BaseModel):
    code: str = Field(description="e.g. ACC101, BIO201")
    name: str
    credits: int
    programme_codes: list[str]
    year_level: int
    semester: Semester
    prerequisites: list[Prerequisite] = []
    is_active: bool = True


class Offering(BaseModel):
    id: str
    course_code: str
    semester: Semester
    year: int
    campus: Campus
    lecturer_name: str | None = None
    lecturer_banner_id: str | None = None
    day_of_week: str
    start_time: str = Field(description="HH:MM 24h format")
    end_time: str = Field(description="HH:MM 24h format")
    room: str
    capacity: int
    enrolled: int = 0


class FeeItem(BaseModel):
    code: str
    description: str
    amount_cents: int
    currency: str = "FJD"
    applies_to: str = Field(description="programme code or 'ALL'")
    fee_type: str = Field(description="tuition | lab | library | registration | exam")


class FeeSchedule(BaseModel):
    year: int
    semester: Semester
    items: list[FeeItem]


class BannerStudent(BaseModel):
    banner_id: str = Field(description="e.g. S00012345")
    first_name: str
    last_name: str
    email: str
    phone: str | None = None
    programme_code: str | None = None
    campus: Campus | None = None
    enrolment_status: str = Field(
        default="active", description="active | suspended | graduated | withdrawn"
    )
    gpa: float | None = None


class Invoice(BaseModel):
    invoice_id: str
    banner_student_id: str
    semester: Semester
    year: int
    items: list[FeeItem]
    total_cents: int
    paid_cents: int = 0
    due_date: date | None = None
    status: str = Field(default="unpaid", description="unpaid | partial | paid | overdue")


class RosterEntry(BaseModel):
    banner_student_id: str
    student_name: str
    email: str
    grade: str | None = None
    attendance_pct: float | None = None


class ClassRoster(BaseModel):
    offering_id: str
    course_code: str
    course_name: str
    semester: Semester
    year: int
    campus: Campus
    entries: list[RosterEntry]


class CompletedCourse(BaseModel):
    course_code: str
    course_name: str
    grade: str
    credits: int
    semester: Semester
    year: int


class CreateStudentRequest(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: str
    phone: str | None = None
    programme_code: str
    campus: Campus


class CreateStudentResponse(BaseModel):
    banner_id: str
    success: bool = True


class RegisterCourseRequest(BaseModel):
    banner_student_id: str
    offering_id: str


class RegisterCourseResponse(BaseModel):
    success: bool
    message: str


class SubmitGradeRequest(BaseModel):
    offering_id: str
    banner_student_id: str
    grade: str = Field(description="e.g. A, B+, C, F, WD")


class SubmitGradeResponse(BaseModel):
    success: bool
    message: str


class CreateInvoiceRequest(BaseModel):
    banner_student_id: str
    semester: Semester
    year: int
    items: list[FeeItem]


class CreateInvoiceResponse(BaseModel):
    invoice_id: str
    total_cents: int
    success: bool = True


class BannerHealthResponse(BaseModel):
    status: str
    latency_ms: float
