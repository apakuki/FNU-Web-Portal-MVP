from pydantic import model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://fnu:fnu_dev_password@localhost:5432/fnu_portal"
    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60
    banner_mode: str = "mock"
    openrouter_api_key: str = ""
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost"]
    environment: str = "development"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @model_validator(mode="after")
    def validate_secrets(self) -> "Settings":
        if self.environment == "production":
            if self.jwt_secret in ("change-me", ""):
                raise ValueError("JWT_SECRET must be set to a secure random value in production")
            if len(self.jwt_secret) < 32:
                raise ValueError("JWT_SECRET must be at least 32 characters in production")
        return self


settings = Settings()
