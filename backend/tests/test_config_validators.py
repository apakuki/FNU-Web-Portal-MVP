"""Tests for Settings.validate_secrets — tightened in Part 16."""

from __future__ import annotations

import pytest

from src.backend.config import Settings

# 64-char hex strings used as placeholder-free replacements. Never deployed.
GOOD_SECRET = "a" * 64
GOOD_ID_CARD = "b" * 64


def _prod(**overrides: object) -> Settings:
    """Build a Settings with production-mode defaults that *should* pass."""
    base: dict[str, object] = dict(
        environment="production",
        jwt_secret=GOOD_SECRET,
        id_card_secret=GOOD_ID_CARD,
        payments_mode="live",
        mpaisa_merchant_id="merchant-mp",
        mpaisa_secret=GOOD_SECRET,
        mycash_merchant_id="merchant-mc",
        mycash_secret=GOOD_SECRET,
        banner_mode="live",
        banner_api_url="https://banner.fnu.ac.fj/ethos",
        banner_api_key="real-banner-token",
        chatbot_mode="live",
        openrouter_api_key="sk-or-v1-realtoken",
        notifications_mode="live",
        smtp_user="apikey",
        smtp_pass="real-smtp-pw",
        sms_provider="stub",
        public_app_url="https://portal.fnu.ac.fj",
    )
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


def test_production_defaults_are_rejected() -> None:
    with pytest.raises(ValueError, match="JWT_SECRET"):
        Settings(environment="production")


@pytest.mark.parametrize(
    "field",
    ["jwt_secret", "id_card_secret"],
)
def test_placeholder_markers_rejected(field: str) -> None:
    for placeholder in ("change-me", "id-card-change-me", "REPLACE-with-64-char-random"):
        with pytest.raises(ValueError):
            _prod(**{field: placeholder})


def test_jwt_secret_too_short_rejected() -> None:
    with pytest.raises(ValueError, match="at least 32"):
        _prod(jwt_secret="x" * 20)


def test_payments_stub_rejected_in_prod() -> None:
    with pytest.raises(ValueError, match="PAYMENTS_MODE=stub"):
        _prod(payments_mode="stub")


def test_payments_secrets_min_length() -> None:
    with pytest.raises(ValueError, match="at least 32"):
        _prod(mpaisa_secret="short-secret")


def test_banner_live_requires_https() -> None:
    with pytest.raises(ValueError, match="https://"):
        _prod(banner_api_url="http://banner.fnu.ac.fj/ethos")


def test_banner_live_requires_api_key() -> None:
    with pytest.raises(ValueError, match="BANNER_API_KEY"):
        _prod(banner_api_key="")


def test_chatbot_live_requires_openrouter_key() -> None:
    with pytest.raises(ValueError, match="OPENROUTER_API_KEY"):
        _prod(openrouter_api_key="sk-or-v1-your-key-here")


def test_notifications_live_requires_smtp_creds() -> None:
    with pytest.raises(ValueError, match="SMTP_USER"):
        _prod(smtp_user="")


def test_vodafone_sms_requires_credentials() -> None:
    with pytest.raises(ValueError, match="SMS_API"):
        _prod(sms_provider="vodafone", sms_api_url="", sms_api_key="")


def test_public_app_url_must_be_https() -> None:
    with pytest.raises(ValueError, match="PUBLIC_APP_URL"):
        _prod(public_app_url="http://portal.fnu.ac.fj")


def test_happy_path_production_passes() -> None:
    settings = _prod()
    assert settings.environment == "production"
    assert settings.payments_mode == "live"


def test_development_skips_validation() -> None:
    # Default dev Settings (all placeholders) must still construct.
    settings = Settings(environment="development")
    assert settings.environment == "development"
    assert settings.jwt_secret == "change-me"
