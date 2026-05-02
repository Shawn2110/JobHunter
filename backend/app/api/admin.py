from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import REPO_ROOT
from app.db import get_session
from app.models import (
    AiCall,
    Contact,
    FitAssessment,
    Job,
    JobRepostHistory,
    JobSource,
    OutreachDraft,
    Profile,
    ProfileHandle,
    Resume,
    SearchQuery,
    TailoredArtifact,
    TailoringBrief,
    TrustAssessment,
    WatchlistCompany,
)

router = APIRouter(prefix="/admin", tags=["admin"])


# Tables we export (in dependency-friendly order). Per Agent.md, the
# user owns their data — export must be exhaustive.
_EXPORT_MODELS = [
    Profile,
    ProfileHandle,
    Resume,
    SearchQuery,
    Job,
    JobSource,
    FitAssessment,
    TrustAssessment,
    JobRepostHistory,
    Contact,
    OutreachDraft,
    TailoringBrief,
    TailoredArtifact,
    WatchlistCompany,
    AiCall,
]


def _row_to_dict(row: Any) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for col in row.__table__.columns:
        v = getattr(row, col.name)
        if isinstance(v, datetime):
            v = v.isoformat()
        out[col.name] = v
    return out


@router.get("/export")
async def export_data(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """Export every row from every user-data table as JSON.

    Per PRD § 6 / Agent.md § 6 — the user owns their data.
    """
    out: dict[str, Any] = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "tables": {},
    }
    for model in _EXPORT_MODELS:
        rows = (await session.execute(select(model))).scalars().all()
        out["tables"][model.__tablename__] = [_row_to_dict(r) for r in rows]
    return out


class WipeRequest(BaseModel):
    confirmation: str = Field(min_length=1)


@router.post("/wipe", status_code=status.HTTP_200_OK)
async def wipe_data(
    payload: WipeRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """Delete every row from every user-data table + every file under
    data/. Requires the literal confirmation 'WIPE' in the body
    (Design.md § 6.4 typed-confirmation pattern).
    """
    if payload.confirmation != "WIPE":
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "To confirm the wipe, POST {\"confirmation\": \"WIPE\"}.",
        )

    deleted: dict[str, int] = {}
    # Delete in reverse FK order so cascades aren't load-bearing.
    for model in reversed(_EXPORT_MODELS):
        rows = (await session.execute(select(model))).scalars().all()
        deleted[model.__tablename__] = len(rows)
        for r in rows:
            await session.delete(r)
    await session.commit()

    # Wipe binary artifacts (resumes, generated PDFs, etc.) — keep the
    # data/ directory itself.
    data_dir = REPO_ROOT / "data"
    files_removed = 0
    if data_dir.exists():
        for entry in data_dir.iterdir():
            if entry.name == ".gitkeep":
                continue
            if entry.is_file():
                entry.unlink()
                files_removed += 1
            elif entry.is_dir():
                shutil.rmtree(entry, ignore_errors=True)
                files_removed += 1

    return {
        "deleted_rows": deleted,
        "files_removed": files_removed,
    }
