"""Payment gateway integration module.

Provides a uniform interface to M-PAiSA, MyCash, and bank transfer, with a stub
adapter for development and testing. Callback verification uses HMAC-SHA256.
"""

from src.backend.payments.base import (
    InitiateRequest,
    InitiateResponse,
    PaymentAdapter,
    PaymentMethod,
    PaymentStatus,
)
from src.backend.payments.factory import get_payment_adapter
from src.backend.payments.plan_engine import generate_plan_schedule
from src.backend.payments.signature import sign_payload, verify_signature

__all__ = [
    "InitiateRequest",
    "InitiateResponse",
    "PaymentAdapter",
    "PaymentMethod",
    "PaymentStatus",
    "get_payment_adapter",
    "generate_plan_schedule",
    "sign_payload",
    "verify_signature",
]
