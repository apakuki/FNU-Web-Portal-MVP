"""Digital ID card QR signing — HMAC-SHA256 over a compact payload.

Payload format (URL-safe base64 of `<json>.<sig>`):
    json   = {"u": <user_uuid>, "b": <banner_id>, "e": <expiry_epoch>}
    sig    = HMAC-SHA256(json_bytes, ID_CARD_SECRET)

Verification re-derives the HMAC and rejects on mismatch / expiry. The QR
payload itself never contains a name, programme, photo, or contact — those
are looked up server-side after the signature checks out.
"""

from __future__ import annotations

import base64
import hmac
import json
import uuid
from datetime import UTC, datetime, timedelta
from hashlib import sha256

from src.backend.config import settings


class InvalidIdCardSignature(Exception):
    pass


class ExpiredIdCard(Exception):
    pass


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    pad = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + pad)


def _hmac(payload_bytes: bytes) -> bytes:
    return hmac.new(
        settings.id_card_secret.encode("utf-8"),
        payload_bytes,
        sha256,
    ).digest()


def sign_id_card(
    *,
    user_id: uuid.UUID,
    banner_id: str,
    validity_days: int | None = None,
) -> tuple[str, datetime]:
    """Return (qr_payload, expires_at). qr_payload is URL-safe."""
    days = validity_days if validity_days is not None else settings.id_card_validity_days
    expires_at = datetime.now(UTC) + timedelta(days=days)
    payload = {
        "u": str(user_id),
        "b": banner_id,
        "e": int(expires_at.timestamp()),
    }
    payload_bytes = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    sig = _hmac(payload_bytes)
    qr = f"{_b64url_encode(payload_bytes)}.{_b64url_encode(sig)}"
    return qr, expires_at


def verify_id_card(qr: str) -> dict:
    """Verify the QR payload. Returns the decoded payload dict on success.

    Raises InvalidIdCardSignature on tamper, ExpiredIdCard on expiry.
    """
    if "." not in qr:
        raise InvalidIdCardSignature("Malformed payload")
    payload_b64, sig_b64 = qr.split(".", 1)

    try:
        payload_bytes = _b64url_decode(payload_b64)
        sig = _b64url_decode(sig_b64)
    except (ValueError, base64.binascii.Error) as exc:
        raise InvalidIdCardSignature("Malformed encoding") from exc

    expected = _hmac(payload_bytes)
    if not hmac.compare_digest(expected, sig):
        raise InvalidIdCardSignature("Signature mismatch")

    try:
        payload = json.loads(payload_bytes)
    except json.JSONDecodeError as exc:
        raise InvalidIdCardSignature("Malformed payload JSON") from exc

    if not isinstance(payload, dict) or "e" not in payload or "u" not in payload:
        raise InvalidIdCardSignature("Missing payload fields")

    if datetime.now(UTC).timestamp() > payload["e"]:
        raise ExpiredIdCard("ID card has expired")

    return payload
