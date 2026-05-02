from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import WatchlistCompany
from app.workers.nightly import crawl_watchlist

router = APIRouter(prefix="/watchlist", tags=["watchlist"])


class WatchlistIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    careers_url: str = Field(min_length=1, max_length=1024)


class WatchlistOut(BaseModel):
    id: int
    name: str
    careers_url: str
    last_crawled_at: datetime | None
    last_diff_at: datetime | None
    last_new_count: int | None
    created_at: datetime


@router.get("", response_model=list[WatchlistOut])
async def list_watchlist(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[WatchlistCompany]:
    rows = (
        await session.execute(
            select(WatchlistCompany).order_by(desc(WatchlistCompany.created_at))
        )
    ).scalars().all()
    return list(rows)


@router.post(
    "",
    response_model=WatchlistOut,
    status_code=status.HTTP_201_CREATED,
)
async def add_company(
    payload: WatchlistIn,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> WatchlistCompany:
    row = WatchlistCompany(name=payload.name, careers_url=payload.careers_url)
    session.add(row)
    try:
        await session.commit()
    except IntegrityError as e:
        await session.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "That careers_url is already on the watchlist.",
        ) from e
    await session.refresh(row)
    return row


@router.delete("/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_company(
    company_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    row = await session.get(WatchlistCompany, company_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not on watchlist")
    await session.delete(row)
    await session.commit()


@router.post("/run-now")
async def run_now(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, int]:
    """Manually trigger the nightly crawl. Useful for testing the
    scheduler's job without waiting for 03:00."""
    total_new = await crawl_watchlist()
    return {"total_new": total_new}
