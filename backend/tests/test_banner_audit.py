"""Part 15 — Banner audit + rate-limit wrapper tests.

Covers:
- AuditedBannerClient writes audit_log rows on every write operation
- Rate limiter bucket acquires tokens and blocks once exhausted
"""

from __future__ import annotations

import time
import uuid
from unittest.mock import AsyncMock, patch

from src.backend.banner.audited_client import AuditedBannerClient, set_banner_actor
from src.backend.banner.rate_limit import _TokenBucket
from src.backend.banner.types import (
    CreateInvoiceRequest,
    FeeItem,
    RegisterCourseRequest,
    RegisterCourseResponse,
    Semester,
    SubmitGradeRequest,
    SubmitGradeResponse,
)


class _FakeBannerClient:
    async def register_course(self, req):
        return RegisterCourseResponse(success=True, message="ok")

    async def submit_grade(self, req):
        return SubmitGradeResponse(success=True, message="ok")

    async def create_invoice(self, req):
        from src.backend.banner.types import CreateInvoiceResponse

        return CreateInvoiceResponse(invoice_id="INV-X-1", total_cents=0, success=True)


async def test_register_course_writes_audit():
    fake = _FakeBannerClient()
    client = AuditedBannerClient(fake)
    set_banner_actor(uuid.uuid4())

    with patch(
        "src.backend.banner.audited_client.write_audit_log", new=AsyncMock()
    ) as mock_audit, patch(
        "src.backend.banner.audited_client.acquire_banner_slot", new=AsyncMock()
    ):
        await client.register_course(
            RegisterCourseRequest(banner_student_id="S123", offering_id="O-1")
        )

    assert mock_audit.await_count == 1
    kwargs = mock_audit.await_args.kwargs
    assert kwargs["action"] == "banner.register_course"
    assert kwargs["target_type"] == "banner_registration"
    assert "S123:O-1" == kwargs["target_id"]


async def test_submit_grade_writes_audit():
    fake = _FakeBannerClient()
    client = AuditedBannerClient(fake)

    with patch(
        "src.backend.banner.audited_client.write_audit_log", new=AsyncMock()
    ) as mock_audit, patch(
        "src.backend.banner.audited_client.acquire_banner_slot", new=AsyncMock()
    ):
        await client.submit_grade(
            SubmitGradeRequest(offering_id="O-1", banner_student_id="S123", grade="A")
        )

    assert mock_audit.await_count == 1
    assert mock_audit.await_args.kwargs["action"] == "banner.submit_grade"


async def test_create_invoice_writes_audit():
    fake = _FakeBannerClient()
    client = AuditedBannerClient(fake)

    req = CreateInvoiceRequest(
        banner_student_id="S123",
        semester=Semester.S1,
        year=2026,
        items=[
            FeeItem(
                code="TUITION",
                description="Tuition",
                amount_cents=100000,
                currency="FJD",
                applies_to="programme",
                fee_type="tuition",
            )
        ],
    )

    with patch(
        "src.backend.banner.audited_client.write_audit_log", new=AsyncMock()
    ) as mock_audit, patch(
        "src.backend.banner.audited_client.acquire_banner_slot", new=AsyncMock()
    ):
        await client.create_invoice(req)

    assert mock_audit.await_count == 1
    kwargs = mock_audit.await_args.kwargs
    assert kwargs["action"] == "banner.create_invoice"
    assert kwargs["target_id"] == "INV-X-1"


async def test_token_bucket_allows_initial_burst():
    bucket = _TokenBucket(rate_per_sec=10.0, burst=5)
    start = time.monotonic()
    for _ in range(5):
        await bucket.acquire()
    elapsed = time.monotonic() - start
    # 5 tokens in the bucket at start — should be ~instant
    assert elapsed < 0.05


async def test_token_bucket_throttles_after_burst():
    bucket = _TokenBucket(rate_per_sec=50.0, burst=2)
    for _ in range(2):
        await bucket.acquire()
    start = time.monotonic()
    await bucket.acquire()
    elapsed = time.monotonic() - start
    # At 50/s the next token takes ~20ms
    assert 0.010 < elapsed < 0.200
