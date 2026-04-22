"""Unit tests for payments: signatures, adapters, plan engine, idempotency logic."""

from __future__ import annotations

import asyncio
from datetime import date

import pytest

from src.backend.payments.base import (
    InitiateRequest,
    PaymentMethod,
    PaymentStatus,
)
from src.backend.payments.bank_transfer_adapter import BankTransferAdapter
from src.backend.payments.plan_engine import (
    apply_payment_to_schedule,
    generate_plan_schedule,
    get_due_reminders,
    mark_overdue,
)
from src.backend.payments.signature import (
    _canonical_payload,
    sign_payload,
    verify_signature,
)
from src.backend.payments.stub_adapter import STUB_SECRET, StubPaymentAdapter


# ---------- signature ----------


def test_canonical_payload_sorts_keys():
    assert _canonical_payload({"b": 2, "a": 1}) == "a=1&b=2"


def test_canonical_payload_handles_nested_and_bool_and_none():
    s = _canonical_payload({"d": None, "c": True, "b": False, "a": {"y": 1, "x": 2}})
    assert s == 'a={"x":2,"y":1}&b=false&c=true&d='


def test_sign_payload_deterministic():
    p = {"id": "x", "amount": 500}
    assert sign_payload(p, "secret") == sign_payload(p, "secret")


def test_sign_payload_requires_secret():
    with pytest.raises(ValueError):
        sign_payload({"x": 1}, "")


def test_verify_signature_roundtrip():
    p = {"order_id": "ord-1", "amount_minor": 1000, "result": "OK"}
    sig = sign_payload(p, "shh")
    assert verify_signature(p, sig, "shh") is True


def test_verify_signature_rejects_tamper():
    p = {"order_id": "ord-1", "amount_minor": 1000}
    sig = sign_payload(p, "shh")
    p_tampered = {**p, "amount_minor": 9999}
    assert verify_signature(p_tampered, sig, "shh") is False


def test_verify_signature_rejects_empty_inputs():
    assert verify_signature({"a": 1}, None, "shh") is False
    assert verify_signature({"a": 1}, "sig", "") is False


def test_verify_signature_is_case_insensitive_on_hex():
    p = {"a": 1}
    sig = sign_payload(p, "s")
    assert verify_signature(p, sig.upper(), "s") is True


# ---------- stub adapter ----------


def test_stub_adapter_rejects_bank_transfer_method():
    with pytest.raises(ValueError):
        StubPaymentAdapter(PaymentMethod.BANK_TRANSFER)


def test_stub_adapter_initiate_returns_reference_and_redirect():
    adapter = StubPaymentAdapter(PaymentMethod.MPAISA)
    req = InitiateRequest(
        payment_id="pid-1",
        invoice_id="inv-1",
        banner_student_id="S123",
        amount_cents=5000,
        currency="FJD",
        callback_url="http://x/cb",
    )
    res = asyncio.run(adapter.initiate(req))
    assert res.gateway_reference.startswith("STUB-MPAISA-")
    assert res.redirect_url is not None
    assert "pid=pid-1" in res.redirect_url
    assert res.status == PaymentStatus.INITIATED


def test_stub_adapter_verify_callback_happy_path():
    adapter = StubPaymentAdapter(PaymentMethod.MYCASH)
    payload = {
        "payment_id": "pid-9",
        "gateway_reference": "STUB-MYCASH-ABCDEF",
        "status": "confirmed",
        "amount_cents": 12345,
    }
    sig = sign_payload(payload, STUB_SECRET)
    result = adapter.verify_callback(payload, sig)
    assert result.status == PaymentStatus.CONFIRMED
    assert result.payment_id == "pid-9"
    assert result.amount_cents == 12345


def test_stub_adapter_rejects_missing_fields():
    adapter = StubPaymentAdapter(PaymentMethod.MPAISA)
    with pytest.raises(ValueError, match="Missing"):
        adapter.verify_callback({"payment_id": "x"}, "sig")


def test_stub_adapter_rejects_bad_signature():
    adapter = StubPaymentAdapter(PaymentMethod.MPAISA)
    payload = {
        "payment_id": "pid",
        "gateway_reference": "ref",
        "status": "confirmed",
        "amount_cents": 100,
    }
    with pytest.raises(ValueError, match="signature"):
        adapter.verify_callback(payload, "deadbeef")


def test_stub_adapter_rejects_bad_status_value():
    adapter = StubPaymentAdapter(PaymentMethod.MPAISA)
    payload = {
        "payment_id": "pid",
        "gateway_reference": "ref",
        "status": "completely_made_up",
        "amount_cents": 100,
    }
    sig = sign_payload(payload, STUB_SECRET)
    with pytest.raises(ValueError, match="Invalid status"):
        adapter.verify_callback(payload, sig)


# ---------- bank transfer adapter ----------


def test_bank_transfer_adapter_emits_instructions():
    adapter = BankTransferAdapter()
    req = InitiateRequest(
        payment_id="pid-1",
        invoice_id="inv-42",
        banner_student_id="S999",
        amount_cents=25000,
        currency="FJD",
        callback_url="n/a",
    )
    res = asyncio.run(adapter.initiate(req))
    assert res.gateway_reference.startswith("FNU-S999-")
    assert res.redirect_url is None
    assert res.extra["bank_name"]
    assert res.extra["account_number"]
    assert res.extra["deposit_reference"] == res.gateway_reference
    assert res.extra["amount_cents"] == 25000


def test_bank_transfer_adapter_rejects_callback():
    adapter = BankTransferAdapter()
    with pytest.raises(NotImplementedError):
        adapter.verify_callback({}, None)


# ---------- plan engine ----------


def test_generate_plan_schedule_splits_evenly():
    s = generate_plan_schedule(
        invoice_id="inv-1",
        total_cents=30000,
        paid_cents=0,
        num_instalments=3,
        first_due_date=date(2026, 5, 1),
    )
    assert len(s.instalments) == 3
    assert [i["amount_cents"] for i in s.instalments] == [10000, 10000, 10000]
    assert [i["due_date"] for i in s.instalments] == [
        "2026-05-01",
        "2026-05-31",
        "2026-06-30",
    ]
    assert s.balance_cents == 30000


def test_generate_plan_schedule_remainder_goes_to_last():
    s = generate_plan_schedule(
        invoice_id="inv-1",
        total_cents=10001,
        paid_cents=0,
        num_instalments=3,
        first_due_date=date(2026, 1, 1),
    )
    amounts = [i["amount_cents"] for i in s.instalments]
    assert sum(amounts) == 10001
    assert amounts[-1] > amounts[0]


def test_generate_plan_schedule_accounts_for_prior_payment():
    s = generate_plan_schedule(
        invoice_id="inv-1",
        total_cents=20000,
        paid_cents=5000,
        num_instalments=3,
        first_due_date=date(2026, 1, 1),
    )
    assert s.balance_cents == 15000
    assert sum(i["amount_cents"] for i in s.instalments) == 15000


def test_generate_plan_schedule_zero_balance_returns_no_instalments():
    s = generate_plan_schedule(
        invoice_id="inv-1",
        total_cents=10000,
        paid_cents=10000,
        num_instalments=3,
        first_due_date=date(2026, 1, 1),
    )
    assert s.instalments == []
    assert s.balance_cents == 0


def test_generate_plan_schedule_rejects_non_positive_count():
    with pytest.raises(ValueError):
        generate_plan_schedule(
            invoice_id="inv-1",
            total_cents=1000,
            paid_cents=0,
            num_instalments=0,
            first_due_date=date(2026, 1, 1),
        )


def test_apply_payment_marks_earliest_instalments_paid():
    s = generate_plan_schedule(
        invoice_id="inv-1",
        total_cents=30000,
        paid_cents=0,
        num_instalments=3,
        first_due_date=date(2026, 1, 1),
    )
    updated = apply_payment_to_schedule(s, 10000)
    assert updated.instalments[0]["status"] == "paid"
    assert updated.instalments[1]["status"] == "upcoming"
    assert updated.paid_cents == 10000
    assert updated.balance_cents == 20000


def test_apply_payment_stops_when_exhausted():
    s = generate_plan_schedule(
        invoice_id="inv-1",
        total_cents=30000,
        paid_cents=0,
        num_instalments=3,
        first_due_date=date(2026, 1, 1),
    )
    updated = apply_payment_to_schedule(s, 21000)
    statuses = [i["status"] for i in updated.instalments]
    assert statuses == ["paid", "paid", "upcoming"]
    assert updated.paid_cents == 20000
    assert updated.balance_cents == 10000


def test_mark_overdue_flips_past_due_upcoming_instalments():
    s = generate_plan_schedule(
        invoice_id="inv-1",
        total_cents=30000,
        paid_cents=0,
        num_instalments=3,
        first_due_date=date(2026, 1, 1),
    )
    updated = mark_overdue(s, today=date(2026, 2, 15))
    statuses = [i["status"] for i in updated.instalments]
    assert statuses == ["overdue", "overdue", "upcoming"]


def test_mark_overdue_leaves_paid_alone():
    s = generate_plan_schedule(
        invoice_id="inv-1",
        total_cents=30000,
        paid_cents=0,
        num_instalments=3,
        first_due_date=date(2026, 1, 1),
    )
    s = apply_payment_to_schedule(s, 10000)
    updated = mark_overdue(s, today=date(2026, 2, 15))
    assert updated.instalments[0]["status"] == "paid"
    assert updated.instalments[1]["status"] == "overdue"


def test_get_due_reminders_returns_instalments_at_reminder_windows():
    s = generate_plan_schedule(
        invoice_id="inv-1",
        total_cents=30000,
        paid_cents=0,
        num_instalments=3,
        first_due_date=date(2026, 5, 1),
    )
    # 3 days before first instalment (2026-05-01) is 2026-04-28
    reminders = get_due_reminders(s, today=date(2026, 4, 28))
    assert len(reminders) == 1
    assert reminders[0]["due_date"] == "2026-05-01"


def test_get_due_reminders_skips_non_upcoming():
    s = generate_plan_schedule(
        invoice_id="inv-1",
        total_cents=30000,
        paid_cents=0,
        num_instalments=3,
        first_due_date=date(2026, 5, 1),
    )
    s = apply_payment_to_schedule(s, 10000)
    reminders = get_due_reminders(s, today=date(2026, 4, 28))
    assert reminders == []


# ---------- factory ----------


def test_factory_returns_bank_transfer_regardless_of_mode():
    from src.backend.payments.factory import get_payment_adapter

    adapter = get_payment_adapter(PaymentMethod.BANK_TRANSFER)
    assert isinstance(adapter, BankTransferAdapter)


def test_factory_returns_stub_in_stub_mode(monkeypatch):
    from src.backend.config import settings
    from src.backend.payments.factory import get_payment_adapter

    monkeypatch.setattr(settings, "payments_mode", "stub")
    adapter = get_payment_adapter(PaymentMethod.MPAISA)
    assert isinstance(adapter, StubPaymentAdapter)
    assert adapter.method == PaymentMethod.MPAISA


def test_factory_rejects_unknown_mode(monkeypatch):
    from src.backend.config import settings
    from src.backend.payments.factory import get_payment_adapter

    monkeypatch.setattr(settings, "payments_mode", "nonsense")
    with pytest.raises(ValueError):
        get_payment_adapter(PaymentMethod.MPAISA)


def test_factory_get_callback_secret_returns_stub_in_stub_mode(monkeypatch):
    from src.backend.config import settings
    from src.backend.payments.factory import get_callback_secret

    monkeypatch.setattr(settings, "payments_mode", "stub")
    assert get_callback_secret(PaymentMethod.MPAISA) == STUB_SECRET
    assert get_callback_secret(PaymentMethod.MYCASH) == STUB_SECRET
