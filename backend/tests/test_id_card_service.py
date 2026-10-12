"""Tests for the HMAC-SHA256 ID card signer."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from src.backend.services import id_card_service


def test_sign_then_verify_roundtrips(monkeypatch):
    monkeypatch.setattr(id_card_service.settings, "id_card_secret", "x" * 32)
    monkeypatch.setattr(id_card_service.settings, "id_card_validity_days", 365)

    user_id = uuid.uuid4()
    qr, expires_at = id_card_service.sign_id_card(
        user_id=user_id, banner_id="S00012345"
    )

    payload = id_card_service.verify_id_card(qr)
    assert payload["u"] == str(user_id)
    assert payload["b"] == "S00012345"
    assert expires_at > datetime.now(UTC)


def test_verify_rejects_tampered_payload(monkeypatch):
    monkeypatch.setattr(id_card_service.settings, "id_card_secret", "y" * 32)
    qr, _ = id_card_service.sign_id_card(
        user_id=uuid.uuid4(), banner_id="S00012345"
    )
    payload_b64, sig_b64 = qr.split(".", 1)

    # Flip a single character in the payload → signature no longer matches.
    hacked = payload_b64[:-1] + ("A" if payload_b64[-1] != "A" else "B")
    with pytest.raises(id_card_service.InvalidIdCardSignatureError):
        id_card_service.verify_id_card(f"{hacked}.{sig_b64}")


def test_verify_rejects_wrong_secret(monkeypatch):
    monkeypatch.setattr(id_card_service.settings, "id_card_secret", "a" * 32)
    qr, _ = id_card_service.sign_id_card(
        user_id=uuid.uuid4(), banner_id="S00012345"
    )
    monkeypatch.setattr(id_card_service.settings, "id_card_secret", "b" * 32)
    with pytest.raises(id_card_service.InvalidIdCardSignatureError):
        id_card_service.verify_id_card(qr)


def test_verify_rejects_expired(monkeypatch):
    monkeypatch.setattr(id_card_service.settings, "id_card_secret", "z" * 32)
    qr, _ = id_card_service.sign_id_card(
        user_id=uuid.uuid4(),
        banner_id="S00012345",
        validity_days=-1,  # already expired
    )
    with pytest.raises(id_card_service.ExpiredIdCardError):
        id_card_service.verify_id_card(qr)


def test_verify_rejects_malformed():
    with pytest.raises(id_card_service.InvalidIdCardSignatureError):
        id_card_service.verify_id_card("not-a-valid-qr")
    with pytest.raises(id_card_service.InvalidIdCardSignatureError):
        id_card_service.verify_id_card("only-one-part.")


def test_expiry_honours_validity_days(monkeypatch):
    monkeypatch.setattr(id_card_service.settings, "id_card_secret", "k" * 32)
    _, expires = id_card_service.sign_id_card(
        user_id=uuid.uuid4(), banner_id="S1", validity_days=30
    )
    # 30 days ±1 hour tolerance
    delta = expires - datetime.now(UTC)
    assert timedelta(days=29, hours=23) < delta < timedelta(days=30, hours=1)
