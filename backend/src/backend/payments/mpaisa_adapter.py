"""M-PAiSA (Vodafone Fiji) adapter — live mode.

Makes HTTPS calls to the M-PAiSA sandbox/production API. Signature verification
uses HMAC-SHA256 with MPAISA_SECRET.

Note: the sandbox endpoint contract is provider-specific — this adapter uses
a reasonable RFC-shaped request/response. Swap field names to match the real
contract once FNU procures sandbox credentials.
"""

from __future__ import annotations

import httpx

from src.backend.payments.base import (
    CallbackResult,
    InitiateRequest,
    InitiateResponse,
    PaymentAdapter,
    PaymentMethod,
    PaymentStatus,
)
from src.backend.payments.signature import sign_payload, verify_signature


class MpaisaAdapter(PaymentAdapter):
    method = PaymentMethod.MPAISA

    def __init__(self, api_url: str, merchant_id: str, secret: str, timeout: float = 10.0) -> None:
        if not api_url or not merchant_id or not secret:
            raise ValueError("MPAISA adapter requires api_url, merchant_id, and secret")
        self.api_url = api_url.rstrip("/")
        self.merchant_id = merchant_id
        self.secret = secret
        self.timeout = timeout

    async def initiate(self, req: InitiateRequest) -> InitiateResponse:
        body = {
            "merchant_id": self.merchant_id,
            "reference": req.payment_id,
            "invoice_id": req.invoice_id,
            "student_id": req.banner_student_id,
            "amount": req.amount_cents / 100,
            "currency": req.currency,
            "callback_url": req.callback_url,
        }
        body["signature"] = sign_payload(body, self.secret)

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(f"{self.api_url}/initiate", json=body)
            resp.raise_for_status()
            data = resp.json()

        return InitiateResponse(
            gateway_reference=str(data["transaction_id"]),
            redirect_url=data.get("redirect_url"),
            status=PaymentStatus.INITIATED,
            extra=data,
        )

    def verify_callback(self, payload: dict, signature: str | None) -> CallbackResult:
        if not verify_signature(payload, signature, self.secret):
            raise ValueError("Invalid M-PAiSA callback signature")

        required = {"reference", "transaction_id", "status", "amount"}
        missing = required - payload.keys()
        if missing:
            raise ValueError(f"Missing callback fields: {sorted(missing)}")

        status_map = {
            "success": PaymentStatus.CONFIRMED,
            "confirmed": PaymentStatus.CONFIRMED,
            "pending": PaymentStatus.PENDING,
            "failed": PaymentStatus.FAILED,
            "declined": PaymentStatus.FAILED,
        }
        status = status_map.get(str(payload["status"]).lower(), PaymentStatus.FAILED)

        return CallbackResult(
            payment_id=str(payload["reference"]),
            gateway_reference=str(payload["transaction_id"]),
            status=status,
            amount_cents=int(float(payload["amount"]) * 100),
            raw_payload=payload,
        )
