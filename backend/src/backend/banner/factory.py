"""Factory for creating the correct BannerClient based on BANNER_MODE.

In production, BANNER_MODE must be "live" — the mock adapter is never used.
"""

import logging

from src.backend.banner.base import BannerClient
from src.backend.banner.cached_client import CachedBannerClient
from src.backend.config import settings

logger = logging.getLogger(__name__)

_instance: BannerClient | None = None


def _validate_banner_config() -> None:
    if settings.environment == "production" and settings.banner_mode == "mock":
        raise ValueError(
            "BANNER_MODE=mock is not allowed in production. "
            "Set BANNER_MODE=live and configure BANNER_API_URL / BANNER_API_KEY."
        )


def get_banner_client() -> BannerClient:
    global _instance
    if _instance is not None:
        return _instance

    _validate_banner_config()

    if settings.banner_mode == "live":
        from src.backend.banner.live_adapter import LiveBannerClient

        if not settings.banner_api_url or not settings.banner_api_key:
            raise ValueError(
                "BANNER_API_URL and BANNER_API_KEY must be set when BANNER_MODE=live"
            )

        inner = LiveBannerClient(
            base_url=settings.banner_api_url,
            api_key=settings.banner_api_key,
            timeout_seconds=settings.banner_timeout_seconds,
        )
        logger.info("Banner client: live (%s)", settings.banner_api_url)
    else:
        from src.backend.banner.mock_adapter import MockBannerClient

        inner = MockBannerClient()
        logger.info("Banner client: mock")

    _instance = CachedBannerClient(inner, ttl_seconds=settings.banner_cache_ttl_seconds)
    return _instance


def reset_banner_client() -> None:
    global _instance
    _instance = None
