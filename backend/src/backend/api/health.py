from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text

from src.backend.banner import get_banner_client
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

    try:
        client = get_banner_client()
        banner_resp = await client.health()
        banner_status = banner_resp.status
    except Exception:
        banner_status = "unavailable"

    overall = "ok" if pg_status == "ok" and banner_status in ("ok", "mock") else "degraded"

    return HealthResponse(status=overall, postgres=pg_status, banner=banner_status)
