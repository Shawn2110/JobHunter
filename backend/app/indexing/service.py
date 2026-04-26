from __future__ import annotations

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.indexing.embedder import Embedder, HashEmbedder, cosine_similarity
from app.models import Job

log = structlog.get_logger("app.indexing.service")


def job_text_for_embedding(job: Job) -> str:
    parts = [job.title, job.company]
    if job.description_md:
        parts.append(job.description_md[:2000])
    return " — ".join(p for p in parts if p)


async def embed_job(
    job: Job,
    embedder: Embedder,
    session: AsyncSession,
) -> list[float]:
    """Compute and persist an embedding for one Job."""
    vec = embedder.embed(job_text_for_embedding(job))
    job.embedding_vector = vec
    await session.commit()
    return vec


async def reindex_pending(
    embedder: Embedder,
    session: AsyncSession,
    batch: int = 50,
) -> int:
    """Embed any Jobs without an embedding_vector. Returns count processed."""
    rows = (
        await session.execute(
            select(Job).where(Job.embedding_vector.is_(None)).limit(batch)
        )
    ).scalars().all()
    for job in rows:
        job.embedding_vector = embedder.embed(job_text_for_embedding(job))
    await session.commit()
    log.info("indexing.reindex", processed=len(rows))
    return len(rows)


async def search_similar(
    text: str,
    embedder: Embedder,
    session: AsyncSession,
    top_k: int = 20,
) -> list[tuple[Job, float]]:
    """In-memory cosine search over all Jobs with an embedding.

    O(n) per query — fine for v1 single-user volumes (1k-10k jobs).
    Swap to a real ANN index when n grows past that.
    """
    target = embedder.embed(text)
    rows = (
        await session.execute(
            select(Job).where(Job.embedding_vector.is_not(None))
        )
    ).scalars().all()
    scored = [
        (job, cosine_similarity(target, job.embedding_vector or []))
        for job in rows
    ]
    scored.sort(key=lambda pair: pair[1], reverse=True)
    return scored[:top_k]


def default_embedder() -> Embedder:
    """Singleton-ish accessor — easy to swap in a real model later."""
    return HashEmbedder()
