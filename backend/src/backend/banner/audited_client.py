"""Decorator that adds audit logging + rate limiting around Banner writes.

Wraps any `BannerClient`. All read paths pass through unchanged. All write
paths acquire a slot from the Banner rate-limit bucket (stays within Ellucian
quotas) and write an `audit_log` row with before/after payloads. The
`actor_user_id` comes from a `ContextVar` set by the API layer; when absent,
the audit row still lands with `actor_user_id=None`.
"""

import logging
from contextvars import ContextVar
from uuid import UUID

from src.backend.banner.base import BannerClient
from src.backend.banner.rate_limit import acquire_banner_slot
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
from src.backend.services.audit_service import write_audit_log

logger = logging.getLogger(__name__)

_actor_ctx: ContextVar[UUID | None] = ContextVar("banner_actor_user_id", default=None)


def set_banner_actor(user_id: UUID | None) -> None:
    """Set the acting user for subsequent Banner writes on this task."""
    _actor_ctx.set(user_id)


class AuditedBannerClient(BannerClient):
    def __init__(self, inner: BannerClient) -> None:
        self._inner = inner

    # Reads — passthrough, still rate-limited to respect quotas
    async def get_programmes(self) -> list[Programme]:
        await acquire_banner_slot()
        return await self._inner.get_programmes()

    async def get_courses(self, programme_code: str | None = None) -> list[Course]:
        await acquire_banner_slot()
        return await self._inner.get_courses(programme_code)

    async def get_offerings(
        self,
        course_code: str | None = None,
        semester: str | None = None,
        year: int | None = None,
    ) -> list[Offering]:
        await acquire_banner_slot()
        return await self._inner.get_offerings(course_code, semester, year)

    async def get_fee_schedule(self, year: int, semester: str) -> FeeSchedule:
        await acquire_banner_slot()
        return await self._inner.get_fee_schedule(year, semester)

    async def get_student(self, banner_id: str) -> BannerStudent | None:
        await acquire_banner_slot()
        return await self._inner.get_student(banner_id)

    async def get_invoices(self, banner_student_id: str) -> list[Invoice]:
        await acquire_banner_slot()
        return await self._inner.get_invoices(banner_student_id)

    async def get_class_roster(self, offering_id: str) -> ClassRoster | None:
        await acquire_banner_slot()
        return await self._inner.get_class_roster(offering_id)

    async def get_completed_courses(self, banner_student_id: str) -> list[CompletedCourse]:
        await acquire_banner_slot()
        return await self._inner.get_completed_courses(banner_student_id)

    async def get_student_registrations(
        self,
        banner_student_id: str,
        semester: str | None = None,
        year: int | None = None,
    ) -> list[Offering]:
        await acquire_banner_slot()
        return await self._inner.get_student_registrations(banner_student_id, semester, year)

    # Writes — rate-limited + audit-logged
    async def create_student(self, req: CreateStudentRequest) -> CreateStudentResponse:
        await acquire_banner_slot()
        result = await self._inner.create_student(req)
        await write_audit_log(
            actor_user_id=_actor_ctx.get(),
            action="banner.create_student",
            target_type="banner_student",
            target_id=result.banner_id,
            before=None,
            after=req.model_dump(mode="json"),
        )
        return result

    async def register_course(self, req: RegisterCourseRequest) -> RegisterCourseResponse:
        await acquire_banner_slot()
        result = await self._inner.register_course(req)
        await write_audit_log(
            actor_user_id=_actor_ctx.get(),
            action="banner.register_course",
            target_type="banner_registration",
            target_id=f"{req.banner_student_id}:{req.offering_id}",
            before=None,
            after={"success": result.success, "message": result.message},
        )
        return result

    async def submit_grade(self, req: SubmitGradeRequest) -> SubmitGradeResponse:
        await acquire_banner_slot()
        result = await self._inner.submit_grade(req)
        await write_audit_log(
            actor_user_id=_actor_ctx.get(),
            action="banner.submit_grade",
            target_type="banner_grade",
            target_id=f"{req.banner_student_id}:{req.offering_id}",
            before=None,
            after={
                "grade": req.grade,
                "offering_id": req.offering_id,
                "success": result.success,
            },
        )
        return result

    async def create_invoice(self, req: CreateInvoiceRequest) -> CreateInvoiceResponse:
        await acquire_banner_slot()
        result = await self._inner.create_invoice(req)
        await write_audit_log(
            actor_user_id=_actor_ctx.get(),
            action="banner.create_invoice",
            target_type="banner_invoice",
            target_id=result.invoice_id,
            before=None,
            after={
                "banner_student_id": req.banner_student_id,
                "total_cents": sum(i.amount_cents for i in req.items),
                "invoice_id": result.invoice_id,
            },
        )
        return result

    async def health(self) -> BannerHealthResponse:
        return await self._inner.health()
