"""Payment adapter interface and shared types."""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class PaymentMethod(StrEnum):
    MPAISA = "mpaisa"
    MYCASH = "mycash"
    BANK_TRANSFER = "bank_transfer"


class PaymentStatus(StrEnum):
    INITIATED = "initiated"
    PENDING = "pending"
    CONFIRMED = "confirmed"
    FAILED = "failed"
    REFUNDED = "refunded"


class InitiateRequest(BaseModel):
    payment_id: str
    invoice_id: str
    banner_student_id: str
    amount_cents: int = Field(gt=0)
    currency: str = "FJD"
    callback_url: str


class InitiateResponse(BaseModel):
    gateway_reference: str
    redirect_url: str | None = None
    status: PaymentStatus = PaymentStatus.INITIATED
    extra: dict[str, Any] = Field(default_factory=dict)


class CallbackResult(BaseModel):
    payment_id: str
    gateway_reference: str
    status: PaymentStatus
    amount_cents: int
    raw_payload: dict[str, Any] = Field(default_factory=dict)


class PaymentAdapter(ABC):
    """Abstract base for all payment providers."""

    method: PaymentMethod

    @abstractmethod
    async def initiate(self, req: InitiateRequest) -> InitiateResponse:
        """Start a payment. Returns redirect URL for the user."""

    @abstractmethod
    def verify_callback(self, payload: dict[str, Any], signature: str | None) -> CallbackResult:
        """Validate a callback payload and its HMAC signature.
        Raises ValueError if signature mismatches or payload is malformed.
        """
