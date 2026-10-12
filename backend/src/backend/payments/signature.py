"""HMAC-SHA256 signature helpers for payment gateway callbacks.

The canonical payload format is a sorted key=value&... string of top-level
fields. Nested objects are JSON-serialised with sorted keys before hashing.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any


def _canonical_payload(payload: dict[str, Any]) -> str:
    """Produce a deterministic string from a payload dict for signing."""
    parts: list[str] = []
    for key in sorted(payload.keys()):
        val = payload[key]
        if isinstance(val, (dict, list)):
            val_str = json.dumps(val, sort_keys=True, separators=(",", ":"))
        elif isinstance(val, bool):
            val_str = "true" if val else "false"
        elif val is None:
            val_str = ""
        else:
            val_str = str(val)
        parts.append(f"{key}={val_str}")
    return "&".join(parts)


def sign_payload(payload: dict[str, Any], secret: str) -> str:
    """Return the lowercase hex HMAC-SHA256 signature for the payload."""
    if not secret:
        raise ValueError("secret is required")
    canonical = _canonical_payload(payload)
    return hmac.new(
        secret.encode("utf-8"),
        canonical.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def verify_signature(payload: dict[str, Any], signature: str | None, secret: str) -> bool:
    """Compare a signature against the computed HMAC using constant-time compare."""
    if not signature or not secret:
        return False
    expected = sign_payload(payload, secret)
    return hmac.compare_digest(expected, signature.lower())
