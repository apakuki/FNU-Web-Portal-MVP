from abc import ABC, abstractmethod

from src.backend.banner.types import (
    BannerHealthResponse,
    BannerStudent,
    ClassRoster,
    CompletedCourse,
    Course,
    CreateInvoiceRequest,
    CreateInvoiceResponse,
    CreateStudentRequest,
    CreateStudentResponse,
    FeeSchedule,
    Invoice,
    Offering,
    Programme,
    RegisterCourseRequest,
    RegisterCourseResponse,
    SubmitGradeRequest,
    SubmitGradeResponse,
)


class BannerClient(ABC):
    """Abstract interface for all Banner operations."""

    # -- reads --

    @abstractmethod
    async def get_programmes(self) -> list[Programme]:
        ...

    @abstractmethod
    async def get_courses(self, programme_code: str | None = None) -> list[Course]:
        ...

    @abstractmethod
    async def get_offerings(
        self, course_code: str | None = None, semester: str | None = None, year: int | None = None
    ) -> list[Offering]:
        ...

    @abstractmethod
    async def get_fee_schedule(self, year: int, semester: str) -> FeeSchedule:
        ...

    @abstractmethod
    async def get_student(self, banner_id: str) -> BannerStudent | None:
        ...

    @abstractmethod
    async def get_invoices(self, banner_student_id: str) -> list[Invoice]:
        ...

    @abstractmethod
    async def get_class_roster(self, offering_id: str) -> ClassRoster | None:
        ...

    @abstractmethod
    async def get_completed_courses(self, banner_student_id: str) -> list[CompletedCourse]:
        ...

    @abstractmethod
    async def get_student_registrations(
        self, banner_student_id: str, semester: str | None = None, year: int | None = None
    ) -> list[Offering]:
        ...

    # -- writes --

    @abstractmethod
    async def create_student(self, req: CreateStudentRequest) -> CreateStudentResponse:
        ...

    @abstractmethod
    async def register_course(self, req: RegisterCourseRequest) -> RegisterCourseResponse:
        ...

    @abstractmethod
    async def submit_grade(self, req: SubmitGradeRequest) -> SubmitGradeResponse:
        ...

    @abstractmethod
    async def create_invoice(self, req: CreateInvoiceRequest) -> CreateInvoiceResponse:
        ...

    # -- health --

    @abstractmethod
    async def health(self) -> BannerHealthResponse:
        ...
