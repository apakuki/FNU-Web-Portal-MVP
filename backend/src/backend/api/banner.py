from fastapi import APIRouter

from src.backend.banner import get_banner_client
from src.backend.banner.types import BannerHealthResponse

router = APIRouter(prefix="/banner", tags=["banner"])


@router.get("/health", response_model=BannerHealthResponse)
async def banner_health() -> BannerHealthResponse:
    client = get_banner_client()
    return await client.health()
