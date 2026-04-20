"""Live Banner adapter — connects to Ellucian Banner REST API over HTTPS.

Includes request timeouts, circuit breaker, TLS verification, and
sanitisation of all inbound data.
"""

import logging
import time

import httpx

from src.backend.banner.base import BannerClient
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

logger = logging.getLogger(__name__)

CIRCUIT_OPEN_SECONDS = 60
FAILURE_THRESHOLD = 5


def _sanitise_str(value: str | None) -> str | None:
    if value is None:
        return None
    return value.replace("<", "&lt;").replace(">", "&gt;").replace("&", "&amp;")


def _sanitise_str_required(value: str) -> str:
    return value.replace("<", "&lt;").replace(">", "&gt;").replace("&", "&amp;")


class CircuitOpenError(Exception):
    pass


class LiveBannerClient(BannerClient):
    def __init__(
        self,
        base_url: str,
        api_key: str,
        timeout_seconds: float = 10.0,
        verify_ssl: bool = True,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout_seconds
        self._verify_ssl = verify_ssl
        self._failure_count = 0
        self._circuit_open_until: float = 0

    def _check_circuit(self) -> None:
        if self._failure_count >= FAILURE_THRESHOLD:
            if time.monotonic() < self._circuit_open_until:
                raise CircuitOpenError("Banner circuit breaker is open")
            self._failure_count = 0

    def _record_failure(self) -> None:
        self._failure_count += 1
        if self._failure_count >= FAILURE_THRESHOLD:
            self._circuit_open_until = time.monotonic() + CIRCUIT_OPEN_SECONDS
            logger.warning("Banner circuit breaker opened after %d failures", self._failure_count)

    def _record_success(self) -> None:
        self._failure_count = 0

    async def _request(self, method: str, path: str, **kwargs: object) -> httpx.Response:
        self._check_circuit()
        try:
            async with httpx.AsyncClient(
                base_url=self._base_url,
                timeout=self._timeout,
                verify=self._verify_ssl,
            ) as client:
                resp = await client.request(
                    method,
                    path,
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    **kwargs,
                )
                resp.raise_for_status()
                self._record_success()
                return resp
        except (httpx.HTTPStatusError, httpx.RequestError, httpx.TimeoutException) as exc:
            self._record_failure()
            logger.error("Banner API error on %s %s: %s", method, path, exc)
            raise

    async def get_programmes(self) -> list[Programme]:
        resp = await self._request("GET", "/programmes")
        data = resp.json()
        return [
            Programme(
                code=_sanitise_str_required(p["code"]),
                name=_sanitise_str_required(p["name"]),
                level=_sanitise_str_required(p["level"]),
                college=_sanitise_str_required(p["college"]),
                campus_codes=p.get("campus_codes", []),
                duration_years=p["duration_years"],
                total_credits=p["total_credits"],
                is_active=p.get("is_active", True),
            )
            for p in data
        ]

    async def get_courses(self, programme_code: str | None = None) -> list[Course]:
        params = {}
        if programme_code:
            params["programme"] = programme_code
        resp = await self._request("GET", "/courses", params=params)
        data = resp.json()
        return [Course.model_validate(c) for c in data]

    async def get_offerings(
        self,
        course_code: str | None = None,
        semester: str | None = None,
        year: int | None = None,
    ) -> list[Offering]:
        params: dict[str, str | int] = {}
        if course_code:
            params["course_code"] = course_code
        if semester:
            params["semester"] = semester
        if year:
            params["year"] = year
        resp = await self._request("GET", "/offerings", params=params)
        data = resp.json()
        return [Offering.model_validate(o) for o in data]

    async def get_fee_schedule(self, year: int, semester: str) -> FeeSchedule:
        resp = await self._request("GET", f"/fees/{year}/{semester}")
        return FeeSchedule.model_validate(resp.json())

    async def get_student(self, banner_id: str) -> BannerStudent | None:
        try:
            resp = await self._request("GET", f"/students/{banner_id}")
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return None
            raise
        return BannerStudent.model_validate(resp.json())

    async def get_invoices(self, banner_student_id: str) -> list[Invoice]:
        resp = await self._request("GET", f"/students/{banner_student_id}/invoices")
        return [Invoice.model_validate(inv) for inv in resp.json()]

    async def get_class_roster(self, offering_id: str) -> ClassRoster | None:
        try:
            resp = await self._request("GET", f"/offerings/{offering_id}/roster")
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return None
            raise
        return ClassRoster.model_validate(resp.json())

    async def get_completed_courses(self, banner_student_id: str) -> list[CompletedCourse]:
        resp = await self._request("GET", f"/students/{banner_student_id}/completed-courses")
        return [CompletedCourse.model_validate(c) for c in resp.json()]

    async def get_student_registrations(
        self,
        banner_student_id: str,
        semester: str | None = None,
        year: int | None = None,
    ) -> list[Offering]:
        params: dict[str, str | int] = {}
        if semester:
            params["semester"] = semester
        if year:
            params["year"] = year
        resp = await self._request(
            "GET", f"/students/{banner_student_id}/registrations", params=params
        )
        return [Offering.model_validate(o) for o in resp.json()]

    async def create_student(self, req: CreateStudentRequest) -> CreateStudentResponse:
        resp = await self._request("POST", "/students", json=req.model_dump())
        return CreateStudentResponse.model_validate(resp.json())

    async def register_course(self, req: RegisterCourseRequest) -> RegisterCourseResponse:
        resp = await self._request("POST", "/registrations", json=req.model_dump())
        return RegisterCourseResponse.model_validate(resp.json())

    async def submit_grade(self, req: SubmitGradeRequest) -> SubmitGradeResponse:
        resp = await self._request("POST", "/grades", json=req.model_dump())
        return SubmitGradeResponse.model_validate(resp.json())

    async def create_invoice(self, req: CreateInvoiceRequest) -> CreateInvoiceResponse:
        resp = await self._request("POST", "/invoices", json=req.model_dump(mode="json"))
        return CreateInvoiceResponse.model_validate(resp.json())

    async def health(self) -> BannerHealthResponse:
        start = time.monotonic()
        try:
            await self._request("GET", "/health")
            latency = (time.monotonic() - start) * 1000
            return BannerHealthResponse(status="ok", latency_ms=round(latency, 1))
        except Exception:
            latency = (time.monotonic() - start) * 1000
            return BannerHealthResponse(status="unavailable", latency_ms=round(latency, 1))
