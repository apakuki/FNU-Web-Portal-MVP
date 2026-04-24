from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text

from src.backend.banner import get_banner_client
from src.backend.config import settings
from src.backend.db.session import async_session_factory
from src.backend.scheduler import scheduler_status

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    postgres: str
    banner: str
    scheduler: str
    version: str = "0.1.0"
    environment: str


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

    sched = scheduler_status()

    overall = (
        "ok"
        if pg_status == "ok" and banner_status in ("ok", "mock") and sched != "error"
        else "degraded"
    )

    return HealthResponse(
        status=overall,
        postgres=pg_status,
        banner=banner_status,
        scheduler=sched,
        environment=settings.environment,
    )
