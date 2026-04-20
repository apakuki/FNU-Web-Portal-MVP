"""Caching wrapper around any BannerClient.

Caches read-only calls for programmes, courses, and fee schedules.
Write operations and student lookups pass through uncached.
"""

from src.backend.banner.base import BannerClient
from src.backend.banner.cache import TTLCache
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


class CachedBannerClient(BannerClient):
    def __init__(self, inner: BannerClient, ttl_seconds: int = 900) -> None:
        self._inner = inner
        self._cache = TTLCache(ttl_seconds=ttl_seconds)

    @property
    def cache(self) -> TTLCache:
        return self._cache

    async def get_programmes(self) -> list[Programme]:
        return await self._cache.get_or_fetch("programmes", self._inner.get_programmes)

    async def get_courses(self, programme_code: str | None = None) -> list[Course]:
        key = f"courses:{programme_code or 'all'}"
        return await self._cache.get_or_fetch(
            key, lambda: self._inner.get_courses(programme_code)
        )

    async def get_offerings(
        self,
        course_code: str | None = None,
        semester: str | None = None,
        year: int | None = None,
    ) -> list[Offering]:
        return await self._inner.get_offerings(course_code, semester, year)

    async def get_fee_schedule(self, year: int, semester: str) -> FeeSchedule:
        key = f"fees:{year}:{semester}"
        return await self._cache.get_or_fetch(
            key, lambda: self._inner.get_fee_schedule(year, semester)
        )

    async def get_student(self, banner_id: str) -> BannerStudent | None:
        return await self._inner.get_student(banner_id)

    async def get_invoices(self, banner_student_id: str) -> list[Invoice]:
        return await self._inner.get_invoices(banner_student_id)

    async def get_class_roster(self, offering_id: str) -> ClassRoster | None:
        return await self._inner.get_class_roster(offering_id)

    async def get_completed_courses(self, banner_student_id: str) -> list[CompletedCourse]:
        return await self._inner.get_completed_courses(banner_student_id)

    async def get_student_registrations(
        self,
        banner_student_id: str,
        semester: str | None = None,
        year: int | None = None,
    ) -> list[Offering]:
        return await self._inner.get_student_registrations(banner_student_id, semester, year)

    async def create_student(self, req: CreateStudentRequest) -> CreateStudentResponse:
        return await self._inner.create_student(req)

    async def register_course(self, req: RegisterCourseRequest) -> RegisterCourseResponse:
        return await self._inner.register_course(req)

    async def submit_grade(self, req: SubmitGradeRequest) -> SubmitGradeResponse:
        return await self._inner.submit_grade(req)

    async def create_invoice(self, req: CreateInvoiceRequest) -> CreateInvoiceResponse:
        return await self._inner.create_invoice(req)

    async def health(self) -> BannerHealthResponse:
        return await self._inner.health()
