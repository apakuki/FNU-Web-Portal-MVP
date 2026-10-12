"""Bank transfer adapter — manual confirmation by finance staff.

Unlike M-PAiSA and MyCash, this has no automated callback. The adapter issues
bank deposit instructions to the student; finance staff confirm receipt
manually via the `/api/payments/bank-confirm` endpoint.
"""

from __future__ import annotations

import secrets as pysecrets
from typing import Any

from src.backend.payments.base import (
    CallbackResult,
    InitiateRequest,
    InitiateResponse,
    PaymentAdapter,
    PaymentMethod,
    PaymentStatus,
)


class BankTransferAdapter(PaymentAdapter):
    method = PaymentMethod.BANK_TRANSFER

    def __init__(
        self,
        bank_name: str = "Bank of South Pacific",
        account_name: str = "Fiji National University",
        account_number: str = "1234-5678-9012",
    ) -> None:
        self.bank_name = bank_name
        self.account_name = account_name
        self.account_number = account_number

    async def initiate(self, req: InitiateRequest) -> InitiateResponse:
        # Reference that the student must include on their bank deposit slip
        deposit_ref = f"FNU-{req.banner_student_id}-{pysecrets.token_hex(3).upper()}"
        return InitiateResponse(
            gateway_reference=deposit_ref,
            redirect_url=None,
            status=PaymentStatus.PENDING,
            extra={
                "bank_name": self.bank_name,
                "account_name": self.account_name,
                "account_number": self.account_number,
                "deposit_reference": deposit_ref,
                "amount_cents": req.amount_cents,
                "invoice_id": req.invoice_id,
            },
        )

    def verify_callback(self, payload: dict[str, Any], signature: str | None) -> CallbackResult:
        raise NotImplementedError(
            "Bank transfer has no automated callback — use POST /api/payments/bank-confirm"
        )
