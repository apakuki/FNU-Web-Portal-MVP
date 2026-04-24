"""APScheduler hook for periodic KPI recomputation (Part 14).

Runs a single async job at a configurable interval
(`KPI_COMPUTE_INTERVAL_MINUTES`, default 60) that re-runs the KPI compute
pass for the current semester. Controlled by `KPI_SCHEDULER_ENABLED` so
tests and CI runs can disable the background job.
"""

from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from src.backend.config import settings
from src.backend.db.session import async_session_factory
from src.backend.services.kpi_service import run_all

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


async def _compute_job() -> None:
    async with async_session_factory() as session:
        try:
            period = await run_all(session)
            logger.info(
                "KPI scheduler: recompute complete for %s → %s", period.start, period.end
            )
        except Exception:  # pragma: no cover - defensive
            logger.exception("KPI scheduler: recompute failed")


def start_scheduler() -> None:
    global _scheduler
    if not settings.kpi_scheduler_enabled:
        logger.info("KPI scheduler disabled via KPI_SCHEDULER_ENABLED=false")
        return
    if _scheduler is not None:
        return
    _scheduler = AsyncIOScheduler(timezone="UTC")
    _scheduler.add_job(
        _compute_job,
        "interval",
        minutes=settings.kpi_compute_interval_minutes,
        id="kpi_compute",
        replace_existing=True,
        next_run_time=None,
    )
    _scheduler.start()
    logger.info(
        "KPI scheduler started (interval=%dm)", settings.kpi_compute_interval_minutes
    )


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("KPI scheduler stopped")
