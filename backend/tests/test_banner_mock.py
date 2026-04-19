"""Tests for the mock Banner adapter — covers all read/write functions."""

import pytest

from src.backend.banner.mock_adapter import MockBannerClient
from src.backend.banner.types import (
    Campus,
    CreateInvoiceRequest,
    CreateStudentRequest,
    FeeItem,
    RegisterCourseRequest,
    Semester,
    SubmitGradeRequest,
)


@pytest.fixture
def client() -> MockBannerClient:
    return MockBannerClient()


async def test_get_programmes(client: MockBannerClient) -> None:
    programmes = await client.get_programmes()
    assert len(programmes) >= 4
    codes = {p.code for p in programmes}
    assert "BCOM" in codes
    assert "BSCI" in codes
    assert "BNUR" in codes
    assert "DIT" in codes


async def test_get_courses_all(client: MockBannerClient) -> None:
    courses = await client.get_courses()
    assert len(courses) >= 10
    codes = {c.code for c in courses}
    assert "ACC101" in codes
    assert "BIO101" in codes


async def test_get_courses_filtered(client: MockBannerClient) -> None:
    courses = await client.get_courses(programme_code="BCOM")
    assert all("BCOM" in c.programme_codes for c in courses)
    assert any(c.code == "ACC101" for c in courses)
    assert not any(c.code == "BIO101" for c in courses)


async def test_get_offerings_all(client: MockBannerClient) -> None:
    offerings = await client.get_offerings()
    assert len(offerings) >= 3


async def test_get_offerings_filtered(client: MockBannerClient) -> None:
    offerings = await client.get_offerings(course_code="ACC101")
    assert len(offerings) == 1
    assert offerings[0].course_code == "ACC101"


async def test_get_offerings_by_semester(client: MockBannerClient) -> None:
    offerings = await client.get_offerings(semester="S1", year=2026)
    assert all(o.semester == Semester.S1 and o.year == 2026 for o in offerings)


async def test_get_fee_schedule(client: MockBannerClient) -> None:
    fees = await client.get_fee_schedule(2026, "S1")
    assert fees.year == 2026
    assert fees.semester == Semester.S1
    assert len(fees.items) >= 5
    tuition_codes = {f.code for f in fees.items if f.fee_type == "tuition"}
    assert "TUI-BCOM" in tuition_codes


async def test_get_fee_schedule_empty(client: MockBannerClient) -> None:
    fees = await client.get_fee_schedule(2025, "S2")
    assert fees.items == []


async def test_get_student_found(client: MockBannerClient) -> None:
    student = await client.get_student("S00012345")
    assert student is not None
    assert student.first_name == "Apisai"
    assert student.programme_code == "BCOM"


async def test_get_student_not_found(client: MockBannerClient) -> None:
    student = await client.get_student("S99999999")
    assert student is None


async def test_get_invoices(client: MockBannerClient) -> None:
    invoices = await client.get_invoices("S00012345")
    assert len(invoices) >= 1
    inv = invoices[0]
    assert inv.banner_student_id == "S00012345"
    assert inv.total_cents > 0


async def test_get_invoices_empty(client: MockBannerClient) -> None:
    invoices = await client.get_invoices("S99999999")
    assert invoices == []


async def test_get_class_roster(client: MockBannerClient) -> None:
    roster = await client.get_class_roster("OFF-2026-S1-ACC101-NAS")
    assert roster is not None
    assert roster.course_code == "ACC101"
    assert len(roster.entries) >= 1


async def test_get_class_roster_not_found(client: MockBannerClient) -> None:
    roster = await client.get_class_roster("OFF-NONEXISTENT")
    assert roster is None


async def test_create_student(client: MockBannerClient) -> None:
    resp = await client.create_student(
        CreateStudentRequest(
            first_name="Tevita",
            last_name="Koroi",
            email="tevita@fnu.ac.fj",
            programme_code="BCOM",
            campus=Campus.NASINU,
        )
    )
    assert resp.success
    assert resp.banner_id.startswith("S")

    student = await client.get_student(resp.banner_id)
    assert student is not None
    assert student.first_name == "Tevita"


async def test_register_course_success(client: MockBannerClient) -> None:
    resp = await client.register_course(
        RegisterCourseRequest(
            banner_student_id="S00012345",
            offering_id="OFF-2026-S1-ACC101-NAS",
        )
    )
    assert resp.success


async def test_register_course_student_not_found(client: MockBannerClient) -> None:
    resp = await client.register_course(
        RegisterCourseRequest(
            banner_student_id="S99999999",
            offering_id="OFF-2026-S1-ACC101-NAS",
        )
    )
    assert not resp.success
    assert "not found" in resp.message.lower()


async def test_register_course_offering_not_found(client: MockBannerClient) -> None:
    resp = await client.register_course(
        RegisterCourseRequest(
            banner_student_id="S00012345",
            offering_id="OFF-NONEXISTENT",
        )
    )
    assert not resp.success


async def test_submit_grade_success(client: MockBannerClient) -> None:
    resp = await client.submit_grade(
        SubmitGradeRequest(
            offering_id="OFF-2026-S1-ACC101-NAS",
            banner_student_id="S00012345",
            grade="B+",
        )
    )
    assert resp.success


async def test_submit_grade_invalid(client: MockBannerClient) -> None:
    resp = await client.submit_grade(
        SubmitGradeRequest(
            offering_id="OFF-2026-S1-ACC101-NAS",
            banner_student_id="S00012345",
            grade="Z",
        )
    )
    assert not resp.success


async def test_create_invoice(client: MockBannerClient) -> None:
    resp = await client.create_invoice(
        CreateInvoiceRequest(
            banner_student_id="S00012345",
            semester=Semester.S2,
            year=2026,
            items=[
                FeeItem(
                    code="TUI-BCOM",
                    description="Tuition",
                    amount_cents=350000,
                    applies_to="BCOM",
                    fee_type="tuition",
                )
            ],
        )
    )
    assert resp.success
    assert resp.total_cents == 350000
    assert resp.invoice_id.startswith("INV-")


async def test_health(client: MockBannerClient) -> None:
    resp = await client.health()
    assert resp.status == "ok"
    assert resp.latency_ms >= 0
