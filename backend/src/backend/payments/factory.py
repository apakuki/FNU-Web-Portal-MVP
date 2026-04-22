"""Payment adapter factory — selects stub or live adapter based on settings."""

from __future__ import annotations

from src.backend.config import settings
from src.backend.payments.bank_transfer_adapter import BankTransferAdapter
from src.backend.payments.base import PaymentAdapter, PaymentMethod
from src.backend.payments.mpaisa_adapter import MpaisaAdapter
from src.backend.payments.mycash_adapter import MycashAdapter
from src.backend.payments.stub_adapter import StubPaymentAdapter


def get_payment_adapter(method: PaymentMethod) -> PaymentAdapter:
    """Return the adapter for a given payment method, honouring PAYMENTS_MODE."""
    if method == PaymentMethod.BANK_TRANSFER:
        return BankTransferAdapter()

    if settings.payments_mode == "stub":
        return StubPaymentAdapter(method)

    if settings.payments_mode == "live":
        if method == PaymentMethod.MPAISA:
            return MpaisaAdapter(
                api_url=settings.mpaisa_api_url,
                merchant_id=settings.mpaisa_merchant_id,
                secret=settings.mpaisa_secret,
            )
        if method == PaymentMethod.MYCASH:
            return MycashAdapter(
                api_url=settings.mycash_api_url,
                merchant_id=settings.mycash_merchant_id,
                secret=settings.mycash_secret,
            )

    raise ValueError(f"Unsupported payments_mode={settings.payments_mode} for {method}")


def get_callback_secret(method: PaymentMethod) -> str:
    """Return the HMAC secret used to verify a callback for the given method."""
    from src.backend.payments.stub_adapter import STUB_SECRET  # noqa: PLC0415

    if settings.payments_mode == "stub":
        return STUB_SECRET
    if method == PaymentMethod.MPAISA:
        return settings.mpaisa_secret
    if method == PaymentMethod.MYCASH:
        return settings.mycash_secret
    raise ValueError(f"No callback secret for {method}")
