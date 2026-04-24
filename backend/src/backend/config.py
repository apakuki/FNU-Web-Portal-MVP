from pydantic import model_validator
from pydantic_settings import BaseSettings

# Placeholder markers from .env.example and .env.production.example. A value
# matching any of these in production means someone copied the template but
# never filled in a real secret — reject at startup rather than silently ship
# with a guessable value.
_PLACEHOLDER_MARKERS = (
    "change-me",
    "id-card-change-me",
    "REPLACE",
    "replace-me",
    "your-key-here",
    "sk-or-v1-your-key-here",
)


def _is_placeholder(value: str) -> bool:
    if not value:
        return True
    lowered = value.lower()
    return any(marker.lower() in lowered for marker in _PLACEHOLDER_MARKERS)


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://fnu:fnu_dev_password@localhost:5432/fnu_portal"
    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60
    banner_mode: str = "mock"
    banner_api_url: str = ""
    banner_api_key: str = ""
    banner_timeout_seconds: float = 10.0
    banner_cache_ttl_seconds: int = 900
    banner_rate_limit_per_sec: float = 20.0
    openrouter_api_key: str = ""
    openrouter_model: str = "anthropic/claude-sonnet-4"
    openrouter_api_url: str = "https://openrouter.ai/api/v1/chat/completions"
    chatbot_mode: str = "stub"  # stub | live
    chatbot_max_message_chars: int = 2000
    chatbot_max_history_turns: int = 50
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost"]
    environment: str = "development"

    payments_mode: str = "stub"
    mpaisa_merchant_id: str = ""
    mpaisa_secret: str = ""
    mpaisa_api_url: str = "https://sandbox.mpaisa.vodafone.com.fj/api"
    mpaisa_callback_url: str = "http://localhost/api/payments/callback/mpaisa"
    mycash_merchant_id: str = ""
    mycash_secret: str = ""
    mycash_api_url: str = "https://sandbox.digicel.com.fj/mycash/api"
    mycash_callback_url: str = "http://localhost/api/payments/callback/mycash"

    # Notifications — Part 11
    smtp_host: str = "sandbox.smtp.mailtrap.io"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_pass: str = ""
    smtp_from: str = "noreply@portal.fnu.ac.fj"
    smtp_use_tls: bool = True
    sms_provider: str = "stub"  # stub | vodafone
    sms_api_url: str = ""
    sms_api_key: str = ""
    sms_from: str = "FNU"
    notifications_mode: str = "stub"  # stub (log only) | live (SMTP/SMS)

    # ID card / QR signing — Part 11
    id_card_secret: str = "id-card-change-me"
    id_card_validity_days: int = 365

    # Profile photo constraints — Part 11
    profile_photo_max_bytes: int = 2 * 1024 * 1024  # 2 MB
    profile_photo_target_size: int = 400  # pixels (square)

    # Public app URL (used in QR verification links) — Part 11
    public_app_url: str = "http://localhost"

    # KPI dashboard — Part 14
    kpi_scheduler_enabled: bool = True
    kpi_compute_interval_minutes: int = 60

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @model_validator(mode="after")
    def validate_secrets(self) -> "Settings":
        if self.environment != "production":
            return self

        if _is_placeholder(self.jwt_secret):
            raise ValueError("JWT_SECRET must be set to a secure random value in production")
        if len(self.jwt_secret) < 32:
            raise ValueError("JWT_SECRET must be at least 32 characters in production")

        if _is_placeholder(self.id_card_secret):
            raise ValueError("ID_CARD_SECRET must be set to a secure random value in production")
        if len(self.id_card_secret) < 32:
            raise ValueError("ID_CARD_SECRET must be at least 32 characters in production")

        if self.payments_mode == "stub":
            raise ValueError("PAYMENTS_MODE=stub is not allowed in production")
        if self.payments_mode == "live":
            for label, value in (
                ("MPAISA_MERCHANT_ID", self.mpaisa_merchant_id),
                ("MPAISA_SECRET", self.mpaisa_secret),
                ("MYCASH_MERCHANT_ID", self.mycash_merchant_id),
                ("MYCASH_SECRET", self.mycash_secret),
            ):
                if _is_placeholder(value):
                    raise ValueError(f"{label} must be set to a real credential in production")
            if len(self.mpaisa_secret) < 32 or len(self.mycash_secret) < 32:
                raise ValueError(
                    "MPAISA_SECRET and MYCASH_SECRET must be at least 32 characters in production"
                )

        if self.banner_mode == "live":
            if _is_placeholder(self.banner_api_key):
                raise ValueError("BANNER_API_KEY required when BANNER_MODE=live in production")
            if not self.banner_api_url.startswith("https://"):
                raise ValueError("BANNER_API_URL must use https:// in production")

        if self.chatbot_mode == "live" and _is_placeholder(self.openrouter_api_key):
            raise ValueError("OPENROUTER_API_KEY required when CHATBOT_MODE=live in production")

        if self.notifications_mode == "live":
            if _is_placeholder(self.smtp_user) or _is_placeholder(self.smtp_pass):
                raise ValueError(
                    "SMTP_USER and SMTP_PASS required when NOTIFICATIONS_MODE=live"
                )
            if self.sms_provider not in ("stub", "vodafone"):
                raise ValueError(f"Unknown SMS_PROVIDER={self.sms_provider}")
            if self.sms_provider == "vodafone" and (
                _is_placeholder(self.sms_api_url) or _is_placeholder(self.sms_api_key)
            ):
                raise ValueError(
                    "SMS_API_URL and SMS_API_KEY required when SMS_PROVIDER=vodafone"
                )

        if not self.public_app_url.startswith("https://"):
            raise ValueError("PUBLIC_APP_URL must use https:// in production")

        return self


settings = Settings()
