from pydantic import model_validator
from pydantic_settings import BaseSettings


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

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @model_validator(mode="after")
    def validate_secrets(self) -> "Settings":
        if self.environment == "production":
            if self.jwt_secret in ("change-me", ""):
                raise ValueError("JWT_SECRET must be set to a secure random value in production")
            if len(self.jwt_secret) < 32:
                raise ValueError("JWT_SECRET must be at least 32 characters in production")
            if self.payments_mode == "stub":
                raise ValueError("PAYMENTS_MODE=stub is not allowed in production")
            if self.payments_mode == "live":
                if not self.mpaisa_merchant_id or not self.mpaisa_secret:
                    raise ValueError("MPAISA_MERCHANT_ID and MPAISA_SECRET required in live mode")
                if not self.mycash_merchant_id or not self.mycash_secret:
                    raise ValueError("MYCASH_MERCHANT_ID and MYCASH_SECRET required in live mode")
            if self.chatbot_mode == "live" and not self.openrouter_api_key:
                raise ValueError("OPENROUTER_API_KEY required when CHATBOT_MODE=live")
        return self


settings = Settings()
