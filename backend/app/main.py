from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api import (
    admin,
    contacts,
    extension,
    health,
    outreach,
    profile,
    search,
    tailoring,
    watchlist,
)
from app.config import settings


def configure_logging() -> None:
    """Configure structlog. Sensitive fields must never be logged — see Agent.md."""
    logging.basicConfig(level=settings.log_level)
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, settings.log_level)
        ),
    )


log = structlog.get_logger("app.main")


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    log.info(
        "jobhunt.startup",
        version=__version__,
        host=settings.host_for_uvicorn(),
        port=settings.backend_port,
        bind_public=settings.bind_public,
        ai_configured=settings.has_ai,
        aggregators=settings.configured_aggregators,
        search_provider=settings.configured_search_provider,
        crawler=settings.configured_crawler,
    )
    if not settings.has_ai:
        log.warning(
            "jobhunt.no_ai_key",
            message=(
                "ANTHROPIC_API_KEY not set — AI features will be unavailable. "
                "Add it to .env when you're ready (required from Phase 1)."
            ),
        )
    if not settings.configured_aggregators:
        log.warning(
            "jobhunt.no_aggregators",
            message=(
                "No job aggregator configured. Set at least one of "
                "JSEARCH_API_KEY, ADZUNA_APP_ID/KEY, JOOBLE_API_KEY, "
                "THEIRSTACK_API_KEY in .env to enable Discovery Mode 1."
            ),
        )
    yield
    log.info("jobhunt.shutdown")


app = FastAPI(
    title="JobHunt",
    version=__version__,
    description="Single-user, self-hosted, AI-augmented job hunt — backend.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(profile.router)
app.include_router(search.router)
app.include_router(tailoring.router)
app.include_router(extension.router)
app.include_router(contacts.router)
app.include_router(outreach.router)
app.include_router(watchlist.router)
app.include_router(admin.router)
