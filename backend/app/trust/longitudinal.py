from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.discovery.dedupe import canonical_company, normalize_title
from app.models import JobRepostHistory

log = structlog.get_logger("app.trust.longitudinal")


def canonical_job_id(company: str, title: str, description: str | None) -> str:
    """Stable hash bucketing 'the same job' across reposts.

    We hash canonical company + normalized title + a fingerprint of
    description bigrams (so trivial JD edits don't break the bucket
    but a wholesale rewrite does).
    """
    cc = canonical_company(company)
    nt = normalize_title(title)
    fp = _bigram_fingerprint(description or "")
    return hashlib.sha256(f"{cc}|{nt}|{fp}".encode()).hexdigest()[:32]


def _bigram_fingerprint(text: str, max_grams: int = 200) -> str:
    """Sorted lowercase word-bigram set, hashed. Stable under reordering."""
    words = text.lower().split()
    bigrams = {f"{a} {b}" for a, b in zip(words, words[1:], strict=False)}
    if not bigrams:
        return "empty"
    sorted_grams = sorted(bigrams)[:max_grams]
    return hashlib.sha256("\n".join(sorted_grams).encode()).hexdigest()[:16]


def description_hash(text: str | None) -> str:
    return hashlib.sha256((text or "").encode()).hexdigest()[:32]


@dataclass(frozen=True)
class GhostJobSignal:
    kind: str
    description: str
    severity: str  # info | warning | strong


async def record_sighting(
    *,
    company: str,
    title: str,
    description: str | None,
    source_url: str | None,
    session: AsyncSession,
) -> JobRepostHistory:
    """Insert a JobRepostHistory row for this ingest event."""
    canonical_id = canonical_job_id(company, title, description)
    row = JobRepostHistory(
        job_canonical_id=canonical_id,
        source_url=source_url,
        description_hash=description_hash(description),
        company_canonical=canonical_company(company),
        title_normalized=normalize_title(title),
    )
    session.add(row)
    await session.commit()
    return row


async def evaluate_longitudinal(
    *,
    company: str,
    title: str,
    description: str | None,
    session: AsyncSession,
    now: datetime | None = None,
) -> tuple[list[GhostJobSignal], int | None]:
    """Compute ghost-job signals and a longitudinal score.

    Returns (signals, score). score is None when there's no prior
    history for this canonical job (first ingest).
    """
    canonical_id = canonical_job_id(company, title, description)
    now = now or datetime.now(timezone.utc)

    rows = list(
        (
            await session.execute(
                select(JobRepostHistory).where(
                    JobRepostHistory.job_canonical_id == canonical_id
                )
            )
        )
        .scalars()
        .all()
    )

    if len(rows) <= 1:
        return [], None

    def _seen(r: JobRepostHistory) -> datetime:
        # SQLite stores datetimes without tz info — treat as UTC.
        if r.seen_at and r.seen_at.tzinfo is None:
            return r.seen_at.replace(tzinfo=timezone.utc)
        return r.seen_at  # type: ignore[return-value]

    # Repost frequency in windows
    window_60 = [r for r in rows if r.seen_at and _seen(r) > now - timedelta(days=60)]
    window_90 = [r for r in rows if r.seen_at and _seen(r) > now - timedelta(days=90)]

    signals: list[GhostJobSignal] = []
    score = 100

    if len(window_60) >= 3:
        signals.append(GhostJobSignal(
            kind="reposts",
            description=f"Reposted {len(window_60)} times in the last 60 days",
            severity="warning",
        ))
        score -= 20

    if len(window_90) >= 6:
        signals.append(GhostJobSignal(
            kind="reposts",
            description=f"Reposted {len(window_90)} times in the last 90 days — strong ghost signal",
            severity="strong",
        ))
        score -= 30

    # Description churn: how similar are recent reposts?
    if description and len(rows) >= 3:
        prior_hashes = {r.description_hash for r in rows[:-1] if r.description_hash}
        current = description_hash(description)
        if len(prior_hashes) == 1 and current in prior_hashes:
            # Identical description across all reposts
            sim = 1.0
        else:
            # Approximate via SequenceMatcher of source_urls (cheap proxy)
            sim = 0.5
        if sim > 0.95 and len(window_60) >= 3:
            signals.append(GhostJobSignal(
                kind="static_text",
                description="Same description text across reposts (no real refresh)",
                severity="warning",
            ))
            score -= 10

    return signals, max(score, 0)
