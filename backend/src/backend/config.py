from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://fnu:fnu_dev_password@localhost:5432/fnu_portal"
    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60
    banner_mode: str = "mock"
    openrouter_api_key: str = ""
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost"]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
