"""Payments API — initiate, callbacks, bank confirmation, reconciliation, account."""

from __future__ import annotations

import csv
import io
import uuid
from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.backend.auth import require_role
from src.backend.banner import get_banner_client
from src.backend.config import settings
from src.backend.db.models import PaymentAttempt, PaymentPlan, User
from src.backend.db.session import get_session
from src.backend.payments import (
    InitiateRequest,
    PaymentMethod,
    PaymentStatus,
    get_payment_adapter,
)
from src.backend.payments.factory import get_callback_secret
from src.backend.payments.plan_engine import generate_plan_schedule
from src.backend.payments.signature import verify_signature
from src.backend.rate_limit import limiter
from src.backend.services.audit_service import write_audit_log
from src.backend.services.notification_service import send_notification

router = APIRouter(tags=["payments"])


# --- Schemas ---


class InitiatePaymentRequest(BaseModel):
    invoice_id: str = Field(min_length=1, max_length=100)
    method: PaymentMethod
    amount_cents: int = Field(gt=0, le=10_000_000)


class InitiatePaymentResponse(BaseModel):
    payment_id: str
    gateway_reference: str
    redirect_url: str | None
    status: PaymentStatus
    extra: dict = Field(default_factory=dict)


class BankConfirmRequest(BaseModel):
    payment_id: str
    bank_reference: str = Field(min_length=1, max_length=100)
    amount_cents: int = Field(gt=0)


class PaymentOut(BaseModel):
    id: str
    user_id: str
    invoice_id: str
    method: str
    amount_cents: int
    currency: str
    gateway_reference: str | None
    status: str
    created_at: datetime


class ReconciliationEntry(BaseModel):
    payment_id: str
    student_banner_id: str | None
    invoice_id: str
    method: str
    amount_cents: int
    status: str
    gateway_reference: str | None
    created_at: str


class ReconciliationReport(BaseModel):
    period_from: str
    period_to: str
    total_confirmed_cents: int
    by_method: dict[str, int]
    entries: list[ReconciliationEntry]


class InstalmentOut(BaseModel):
    due_date: str
    amount_cents: int
    status: str


class AccountSummary(BaseModel):
    balance_cents: int
    currency: str
    payment_history: list[PaymentOut]
    instalment_schedule: list[InstalmentOut]


# --- Helpers ---


async def _get_invoice_balance(banner_student_id: str, invoice_id: str) -> tuple[int, int]:
    """Return (total_cents, balance_cents) for a Banner invoice. Raises 404 if unknown."""
    banner = get_banner_client()
    invoices = await banner.get_invoices(banner_student_id)
    inv = next((i for i in invoices if i.invoice_id == invoice_id), None)
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return inv.total_cents, inv.total_cents - inv.paid_cents


# --- Endpoints ---


@router.post("/api/payments/initiate", response_model=InitiatePaymentResponse)
@limiter.limit("10/minute")
async def initiate_payment(
    request: Request,
    body: InitiatePaymentRequest,
    user: User = Depends(require_role("student")),
    db: AsyncSession = Depends(get_session),
) -> InitiatePaymentResponse:
    if not user.banner_id:
        raise HTTPException(status_code=400, detail="No Banner ID linked to account")

    total_cents, balance_cents = await _get_invoice_balance(user.banner_id, body.invoice_id)
    if body.amount_cents > balance_cents:
        raise HTTPException(
            status_code=400,
            detail=f"Amount exceeds outstanding balance ({balance_cents} cents)",
        )

    payment_id = str(uuid.uuid4())
    callback_url = (
        settings.mpaisa_callback_url
        if body.method == PaymentMethod.MPAISA
        else settings.mycash_callback_url
        if body.method == PaymentMethod.MYCASH
        else "n/a"
    )

    adapter = get_payment_adapter(body.method)
    try:
        result = await adapter.initiate(InitiateRequest(
            payment_id=payment_id,
            invoice_id=body.invoice_id,
            banner_student_id=user.banner_id,
            amount_cents=body.amount_cents,
            currency="FJD",
            callback_url=callback_url,
        ))
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Gateway unavailable") from exc

    attempt = PaymentAttempt(
        id=uuid.UUID(payment_id),
        user_id=user.id,
        banner_invoice_id=body.invoice_id,
        method=body.method.value,
        amount_cents=body.amount_cents,
        currency="FJD",
        gateway_reference=result.gateway_reference,
        status=result.status.value,
        callback_payload=None,
    )
    db.add(attempt)
    await db.commit()

    await write_audit_log(
        actor_user_id=user.id,
        action="payment.initiate",
        target_type="payment",
        target_id=payment_id,
        after={
            "method": body.method.value,
            "amount_cents": body.amount_cents,
            "invoice_id": body.invoice_id,
        },
        ip_address=request.client.host if request.client else None,
    )

    return InitiatePaymentResponse(
        payment_id=payment_id,
        gateway_reference=result.gateway_reference,
        redirect_url=result.redirect_url,
        status=result.status,
        extra=result.extra,
    )


async def _handle_callback(
    request: Request,
    method: PaymentMethod,
    payload: dict,
    signature: str | None,
    db: AsyncSession,
) -> dict:
    """Shared logic for M-PAiSA and MyCash callbacks — idempotent by gateway_reference."""
    secret = get_callback_secret(method)

    # Signature goes in a separate header OR embedded in the payload (as in the stub).
    sig = signature or payload.get("signature")
    payload_for_verify = {k: v for k, v in payload.items() if k != "signature"}

    if not verify_signature(payload_for_verify, sig, secret):
        raise HTTPException(status_code=400, detail="Invalid signature")

    adapter = get_payment_adapter(method)
    try:
        result = adapter.verify_callback(payload_for_verify, sig)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # Idempotency: if this gateway_reference already landed, return the existing state
    existing = await db.scalar(
        select(PaymentAttempt).where(
            PaymentAttempt.gateway_reference == result.gateway_reference
        )
    )
    if existing and existing.status == result.status.value:
        return {"detail": "Already processed", "payment_id": str(existing.id)}

    attempt = await db.scalar(
        select(PaymentAttempt).where(PaymentAttempt.id == uuid.UUID(result.payment_id))
    )
    if not attempt:
        raise HTTPException(status_code=404, detail="Payment not found")

    attempt.status = result.status.value
    attempt.callback_payload = payload
    attempt.gateway_reference = result.gateway_reference
    await db.commit()

    if result.status == PaymentStatus.CONFIRMED:
        await send_notification(
            channel="email",
            recipient_user_id=attempt.user_id,
            subject="Payment Confirmed",
            body=f"Your payment of FJ${result.amount_cents / 100:.2f} for invoice "
                 f"{attempt.banner_invoice_id} has been confirmed.",
            template_code="payment_confirmed",
        )

    await write_audit_log(
        actor_user_id=None,
        action="payment.callback",
        target_type="payment",
        target_id=str(attempt.id),
        after={"status": result.status.value, "gateway_reference": result.gateway_reference},
        ip_address=request.client.host if request.client else None,
    )

    return {"detail": "Callback processed", "payment_id": str(attempt.id)}


@router.post("/api/payments/callback/mpaisa")
async def mpaisa_callback(
    request: Request,
    db: AsyncSession = Depends(get_session),
    x_mpaisa_signature: str | None = Header(default=None),
) -> dict:
    payload = await request.json()
    return await _handle_callback(request, PaymentMethod.MPAISA, payload, x_mpaisa_signature, db)


@router.post("/api/payments/callback/mycash")
async def mycash_callback(
    request: Request,
    db: AsyncSession = Depends(get_session),
    x_mycash_signature: str | None = Header(default=None),
) -> dict:
    payload = await request.json()
    return await _handle_callback(request, PaymentMethod.MYCASH, payload, x_mycash_signature, db)


@router.post("/api/payments/bank-confirm")
async def bank_confirm(
    request: Request,
    body: BankConfirmRequest,
    user: User = Depends(require_role("finance", "admin")),
    db: AsyncSession = Depends(get_session),
) -> dict:
    try:
        payment_uuid = uuid.UUID(body.payment_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid payment_id") from exc

    attempt = await db.scalar(
        select(PaymentAttempt).where(PaymentAttempt.id == payment_uuid)
    )
    if not attempt:
        raise HTTPException(status_code=404, detail="Payment not found")
    if attempt.method != PaymentMethod.BANK_TRANSFER.value:
        raise HTTPException(status_code=400, detail="Not a bank transfer payment")
    if attempt.status == PaymentStatus.CONFIRMED.value:
        return {"detail": "Already confirmed"}

    before = {"status": attempt.status}
    attempt.status = PaymentStatus.CONFIRMED.value
    attempt.gateway_reference = body.bank_reference
    attempt.confirmed_by_staff_id = user.id
    attempt.callback_payload = {
        "bank_reference": body.bank_reference,
        "confirmed_amount_cents": body.amount_cents,
    }
    await db.commit()

    await write_audit_log(
        actor_user_id=user.id,
        action="payment.bank_confirm",
        target_type="payment",
        target_id=str(attempt.id),
        before=before,
        after={"status": "confirmed", "bank_reference": body.bank_reference},
        ip_address=request.client.host if request.client else None,
    )

    await send_notification(
        channel="email",
        recipient_user_id=attempt.user_id,
        subject="Bank Transfer Confirmed",
        body=f"Your bank transfer of FJ${body.amount_cents / 100:.2f} for invoice "
             f"{attempt.banner_invoice_id} has been received.",
        template_code="payment_confirmed",
    )

    return {"detail": "Confirmed", "payment_id": str(attempt.id)}


@router.get("/api/payments/reconciliation", response_model=ReconciliationReport)
async def reconciliation(
    date_from: str | None = None,
    date_to: str | None = None,
    method: str | None = None,
    format: str = "json",
    user: User = Depends(require_role("finance", "admin")),
    db: AsyncSession = Depends(get_session),
):
    try:
        dt_from = datetime.fromisoformat(date_from) if date_from else datetime.now(UTC) - timedelta(days=30)
        dt_to = datetime.fromisoformat(date_to) if date_to else datetime.now(UTC)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid date format (use ISO 8601)") from exc

    if dt_from.tzinfo is None:
        dt_from = dt_from.replace(tzinfo=UTC)
    if dt_to.tzinfo is None:
        dt_to = dt_to.replace(tzinfo=UTC)

    conditions = [
        PaymentAttempt.created_at >= dt_from,
        PaymentAttempt.created_at <= dt_to,
    ]
    if method:
        conditions.append(PaymentAttempt.method == method)

    attempts = (
        await db.scalars(
            select(PaymentAttempt)
            .where(and_(*conditions))
            .order_by(PaymentAttempt.created_at.desc())
        )
    ).all()

    user_ids = {a.user_id for a in attempts}
    users = {
        u.id: u
        for u in (await db.scalars(select(User).where(User.id.in_(user_ids)))).all()
    }

    by_method: dict[str, int] = {}
    total_confirmed = 0
    entries: list[ReconciliationEntry] = []
    for a in attempts:
        u = users.get(a.user_id)
        if a.status == PaymentStatus.CONFIRMED.value:
            total_confirmed += a.amount_cents
            by_method[a.method] = by_method.get(a.method, 0) + a.amount_cents
        entries.append(ReconciliationEntry(
            payment_id=str(a.id),
            student_banner_id=u.banner_id if u else None,
            invoice_id=a.banner_invoice_id,
            method=a.method,
            amount_cents=a.amount_cents,
            status=a.status,
            gateway_reference=a.gateway_reference,
            created_at=a.created_at.isoformat(),
        ))

    if format == "csv":
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow([
            "payment_id", "student_banner_id", "invoice_id",
            "method", "amount_cents", "status", "gateway_reference", "created_at",
        ])
        for e in entries:
            writer.writerow([
                e.payment_id, e.student_banner_id or "", e.invoice_id,
                e.method, e.amount_cents, e.status,
                e.gateway_reference or "", e.created_at,
            ])
        buf.seek(0)
        return StreamingResponse(
            iter([buf.getvalue()]),
            media_type="text/csv",
            headers={
                "Content-Disposition": 'attachment; filename="reconciliation.csv"',
            },
        )

    return ReconciliationReport(
        period_from=dt_from.isoformat(),
        period_to=dt_to.isoformat(),
        total_confirmed_cents=total_confirmed,
        by_method=by_method,
        entries=entries,
    )


@router.get("/api/account", response_model=AccountSummary)
async def get_account(
    user: User = Depends(require_role("student")),
    db: AsyncSession = Depends(get_session),
) -> AccountSummary:
    if not user.banner_id:
        raise HTTPException(status_code=400, detail="No Banner ID linked to account")

    banner = get_banner_client()
    invoices = await banner.get_invoices(user.banner_id)
    balance = sum((i.total_cents - i.paid_cents) for i in invoices)

    attempts = (
        await db.scalars(
            select(PaymentAttempt)
            .where(PaymentAttempt.user_id == user.id)
            .order_by(PaymentAttempt.created_at.desc())
            .limit(20)
        )
    ).all()

    history = [
        PaymentOut(
            id=str(a.id),
            user_id=str(a.user_id),
            invoice_id=a.banner_invoice_id,
            method=a.method,
            amount_cents=a.amount_cents,
            currency=a.currency,
            gateway_reference=a.gateway_reference,
            status=a.status,
            created_at=a.created_at,
        )
        for a in attempts
    ]

    plan = await db.scalar(
        select(PaymentPlan)
        .where(PaymentPlan.user_id == user.id)
        .order_by(PaymentPlan.created_at.desc())
        .limit(1)
    )
    instalments: list[InstalmentOut] = []
    if plan and plan.schedule:
        schedule_data = plan.schedule.get("instalments", [])
        today = date.today()
        for inst in schedule_data:
            instalments.append(InstalmentOut(
                due_date=inst["due_date"],
                amount_cents=inst["amount_cents"],
                status=(
                    "overdue"
                    if inst["status"] == "upcoming" and date.fromisoformat(inst["due_date"]) < today
                    else inst["status"]
                ),
            ))

    return AccountSummary(
        balance_cents=balance,
        currency="FJD",
        payment_history=history,
        instalment_schedule=instalments,
    )


class CreatePlanRequest(BaseModel):
    invoice_id: str
    num_instalments: int = Field(ge=2, le=6)
    first_due_date: str  # ISO date


@router.post("/api/account/plan")
async def create_payment_plan(
    request: Request,
    body: CreatePlanRequest,
    user: User = Depends(require_role("student")),
    db: AsyncSession = Depends(get_session),
) -> dict:
    if not user.banner_id:
        raise HTTPException(status_code=400, detail="No Banner ID linked to account")

    total_cents, balance_cents = await _get_invoice_balance(user.banner_id, body.invoice_id)
    if balance_cents <= 0:
        raise HTTPException(status_code=400, detail="Invoice already paid")

    try:
        first_due = date.fromisoformat(body.first_due_date)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid first_due_date") from exc

    schedule = generate_plan_schedule(
        invoice_id=body.invoice_id,
        total_cents=total_cents,
        paid_cents=total_cents - balance_cents,
        num_instalments=body.num_instalments,
        first_due_date=first_due,
    )

    plan = PaymentPlan(
        user_id=user.id,
        banner_invoice_id=body.invoice_id,
        schedule=schedule.model_dump(),
        deregistration_warning_week=4,
    )
    db.add(plan)
    await db.commit()

    await write_audit_log(
        actor_user_id=user.id,
        action="payment.plan.create",
        target_type="payment_plan",
        target_id=str(plan.id),
        after={"invoice_id": body.invoice_id, "instalments": body.num_instalments},
        ip_address=request.client.host if request.client else None,
    )

    return {"plan_id": str(plan.id), "schedule": schedule.model_dump()}
