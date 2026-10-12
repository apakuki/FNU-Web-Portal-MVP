"""MyCash (Digicel Fiji) adapter — live mode.

Shape mirrors the M-PAiSA adapter with MyCash-specific field names. Swap to
match the final Digicel contract once credentials arrive.
"""

from __future__ import annotations

from typing import Any

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


class MycashAdapter(PaymentAdapter):
    method = PaymentMethod.MYCASH

    def __init__(self, api_url: str, merchant_id: str, secret: str, timeout: float = 10.0) -> None:
        if not api_url or not merchant_id or not secret:
            raise ValueError("MyCash adapter requires api_url, merchant_id, and secret")
        self.api_url = api_url.rstrip("/")
        self.merchant_id = merchant_id
        self.secret = secret
        self.timeout = timeout

    async def initiate(self, req: InitiateRequest) -> InitiateResponse:
        body = {
            "merchant": self.merchant_id,
            "order_id": req.payment_id,
            "invoice": req.invoice_id,
            "customer_id": req.banner_student_id,
            "amount_minor": req.amount_cents,
            "currency": req.currency,
            "return_url": req.callback_url,
        }
        body["signature"] = sign_payload(body, self.secret)

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(f"{self.api_url}/transactions", json=body)
            resp.raise_for_status()
            data = resp.json()

        return InitiateResponse(
            gateway_reference=str(data["txn_id"]),
            redirect_url=data.get("payment_url"),
            status=PaymentStatus.INITIATED,
            extra=data,
        )

    def verify_callback(self, payload: dict[str, Any], signature: str | None) -> CallbackResult:
        if not verify_signature(payload, signature, self.secret):
            raise ValueError("Invalid MyCash callback signature")

        required = {"order_id", "txn_id", "result", "amount_minor"}
        missing = required - payload.keys()
        if missing:
            raise ValueError(f"Missing callback fields: {sorted(missing)}")

        status_map = {
            "OK": PaymentStatus.CONFIRMED,
            "APPROVED": PaymentStatus.CONFIRMED,
            "PENDING": PaymentStatus.PENDING,
            "DECLINED": PaymentStatus.FAILED,
            "FAILED": PaymentStatus.FAILED,
        }
        status = status_map.get(str(payload["result"]).upper(), PaymentStatus.FAILED)

        return CallbackResult(
            payment_id=str(payload["order_id"]),
            gateway_reference=str(payload["txn_id"]),
            status=status,
            amount_cents=int(payload["amount_minor"]),
            raw_payload=payload,
        )
