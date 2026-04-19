from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text

from src.backend.db.session import async_session_factory

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    postgres: str
    banner: str


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    pg_status = "ok"
    try:
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
    except Exception:
        pg_status = "unavailable"

    banner_status = "mock"

    return HealthResponse(status="ok", postgres=pg_status, banner=banner_status)
