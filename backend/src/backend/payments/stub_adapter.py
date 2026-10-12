"""Stub payment adapter — used when PAYMENTS_MODE=stub.

Simulates the gateway lifecycle without making external calls. Generates a
deterministic gateway reference, returns a "redirect URL" that points to the
portal's own success callback, and signs payloads with a local secret so
callback verification can be exercised end-to-end in tests.
"""

from __future__ import annotations

import secrets as pysecrets
from typing import Any, ClassVar

from src.backend.payments.base import (
    CallbackResult,
    InitiateRequest,
    InitiateResponse,
    PaymentAdapter,
    PaymentMethod,
    PaymentStatus,
)
from src.backend.payments.signature import verify_signature

STUB_SECRET = "stub-payments-secret-for-dev-only-do-not-use-in-production"


class StubPaymentAdapter(PaymentAdapter):
    """Simulates M-PAiSA / MyCash for local dev and CI."""

    SUPPORTED_METHODS: ClassVar[set[PaymentMethod]] = {
        PaymentMethod.MPAISA,
        PaymentMethod.MYCASH,
    }

    def __init__(self, method: PaymentMethod) -> None:
        if method not in self.SUPPORTED_METHODS:
            raise ValueError(f"Stub adapter does not support {method}")
        self.method = method
        self.secret = STUB_SECRET

    async def initiate(self, req: InitiateRequest) -> InitiateResponse:
        gateway_ref = f"STUB-{self.method.value.upper()}-{pysecrets.token_hex(6).upper()}"
        redirect = (
            f"/api/payments/callback/{self.method.value}"
            f"?ref={gateway_ref}&pid={req.payment_id}&stub=1"
        )
        return InitiateResponse(
            gateway_reference=gateway_ref,
            redirect_url=redirect,
            status=PaymentStatus.INITIATED,
            extra={"stub": True, "callback_url": req.callback_url},
        )

    def verify_callback(self, payload: dict[str, Any], signature: str | None) -> CallbackResult:
        required = {"payment_id", "gateway_reference", "status", "amount_cents"}
        missing = required - payload.keys()
        if missing:
            raise ValueError(f"Missing callback fields: {sorted(missing)}")

        if not verify_signature(payload, signature, self.secret):
            raise ValueError("Invalid callback signature")

        try:
            status = PaymentStatus(payload["status"])
        except ValueError as exc:
            raise ValueError(f"Invalid status: {payload['status']}") from exc

        return CallbackResult(
            payment_id=str(payload["payment_id"]),
            gateway_reference=str(payload["gateway_reference"]),
            status=status,
            amount_cents=int(payload["amount_cents"]),
            raw_payload=payload,
        )
