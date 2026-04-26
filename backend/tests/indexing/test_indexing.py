from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.indexing.embedder import HashEmbedder, cosine_similarity
from app.indexing.service import (
    embed_job,
    reindex_pending,
    search_similar,
)
from app.models import Job


def test_hash_embedder_dim_and_normalization() -> None:
    e = HashEmbedder()
    v = e.embed("Hello world")
    assert len(v) == 384
    norm = sum(x * x for x in v) ** 0.5
    assert abs(norm - 1.0) < 1e-6


def test_hash_embedder_deterministic() -> None:
    e = HashEmbedder()
    assert e.embed("hello") == e.embed("hello")


def test_hash_embedder_empty() -> None:
    e = HashEmbedder()
    v = e.embed("")
    assert len(v) == 384
    # All zeros for empty (no n-grams) → norm 0
    assert all(x == 0 for x in v)


def test_cosine_similarity() -> None:
    assert cosine_similarity([1, 0], [1, 0]) == 1.0
    assert cosine_similarity([1, 0], [0, 1]) == 0.0
    assert abs(cosine_similarity([1, 1], [1, 1]) - 1.0) < 1e-9


def test_cosine_dim_mismatch_raises() -> None:
    with pytest.raises(ValueError, match="dim mismatch"):
        cosine_similarity([1, 0], [1, 0, 0])


@pytest.mark.asyncio
async def test_embed_job_persists_vector(db_session: AsyncSession) -> None:
    job = Job(
        title="Senior Engineer",
        company="Acme",
        company_canonical="acme",
        description_md="Build payment systems",
    )
    db_session.add(job)
    await db_session.commit()

    vec = await embed_job(job, HashEmbedder(), db_session)
    assert len(vec) == 384
    assert job.embedding_vector == vec


@pytest.mark.asyncio
async def test_reindex_pending_processes_unembedded_only(
    db_session: AsyncSession,
) -> None:
    e = HashEmbedder()
    db_session.add_all([
        Job(title="A", company="X", company_canonical="x"),
        Job(title="B", company="X", company_canonical="x", embedding_vector=[0.0] * 384),
        Job(title="C", company="X", company_canonical="x"),
    ])
    await db_session.commit()
    processed = await reindex_pending(e, db_session)
    assert processed == 2  # B was already embedded


@pytest.mark.asyncio
async def test_search_similar_orders_by_relevance(
    db_session: AsyncSession,
) -> None:
    e = HashEmbedder()
    jobs = [
        Job(title="Python backend developer", company="A", company_canonical="a"),
        Job(title="Java microservices engineer", company="B", company_canonical="b"),
        Job(title="Senior Python engineer", company="C", company_canonical="c"),
    ]
    db_session.add_all(jobs)
    await db_session.commit()
    for j in jobs:
        await embed_job(j, e, db_session)

    results = await search_similar("Python developer", e, db_session, top_k=3)
    titles_in_order = [job.title for job, _ in results]
    # Both Python jobs should rank above the Java one
    java_idx = titles_in_order.index("Java microservices engineer")
    python_idx_1 = titles_in_order.index("Python backend developer")
    python_idx_2 = titles_in_order.index("Senior Python engineer")
    assert min(python_idx_1, python_idx_2) < java_idx
