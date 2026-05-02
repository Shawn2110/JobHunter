from __future__ import annotations

import asyncio

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.workers.nightly import crawl_watchlist

log = structlog.get_logger("app.workers.scheduler")


_scheduler: AsyncIOScheduler | None = None


def start_scheduler() -> AsyncIOScheduler:
    """Start the in-process APScheduler. Idempotent — calling twice
    returns the existing scheduler.

    Schedule: nightly watchlist crawl at 03:00 local time.
    """
    global _scheduler
    if _scheduler is not None:
        return _scheduler

    sched = AsyncIOScheduler()
    sched.add_job(
        crawl_watchlist,
        CronTrigger(hour=3, minute=0),
        id="nightly_watchlist",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    sched.start()
    _scheduler = sched
    log.info("scheduler.started", jobs=[j.id for j in sched.get_jobs()])
    return sched


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        log.info("scheduler.stopped")


async def runner() -> None:
    """Entrypoint for the worker container.

    docker-compose.yml runs `python -m app.workers.runner`; this module
    sleeps forever while the scheduler fires jobs in the same event loop.
    """
    start_scheduler()
    while True:
        await asyncio.sleep(3600)
