from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Profile, ProfileHandle


@pytest.mark.asyncio
async def test_insert_and_query_profile(db_session: AsyncSession) -> None:
    profile = Profile(
        name="Test User",
        headline="Backend engineer",
        about_me_text="Looking for fintech roles in Bengaluru",
        target_seniority="senior",
        work_authorization={"IN": "citizen", "US": "needs_sponsorship"},
        salary_floor=4000000,
        salary_currency="INR",
        notice_period_days=60,
        anti_preferences={"industries": ["adtech", "gambling"]},
    )
    db_session.add(profile)
    await db_session.commit()

    result = await db_session.execute(select(Profile))
    fetched = result.scalar_one()
    assert fetched.name == "Test User"
    assert fetched.work_authorization == {"IN": "citizen", "US": "needs_sponsorship"}
    assert fetched.anti_preferences == {"industries": ["adtech", "gambling"]}
    assert fetched.created_at is not None


@pytest.mark.asyncio
async def test_profile_handles_relationship(db_session: AsyncSession) -> None:
    profile = Profile(name="U", handles=[
        ProfileHandle(kind="github", username="shawn", url="https://github.com/shawn"),
        ProfileHandle(kind="leetcode", username="shawn", url="https://leetcode.com/shawn"),
    ])
    db_session.add(profile)
    await db_session.commit()

    fetched = (await db_session.execute(select(Profile))).scalar_one()
    kinds = {h.kind for h in fetched.handles}
    assert kinds == {"github", "leetcode"}


@pytest.mark.asyncio
async def test_handle_kind_unique_per_profile(db_session: AsyncSession) -> None:
    profile = Profile(name="U", handles=[
        ProfileHandle(kind="github", url="https://github.com/a"),
    ])
    db_session.add(profile)
    await db_session.commit()

    # Adding a second 'github' handle for the same profile must fail.
    profile.handles.append(ProfileHandle(kind="github", url="https://github.com/b"))
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_cascade_delete_handles(db_session: AsyncSession) -> None:
    profile = Profile(name="U", handles=[
        ProfileHandle(kind="github", url="https://github.com/a"),
    ])
    db_session.add(profile)
    await db_session.commit()

    await db_session.delete(profile)
    await db_session.commit()

    handles = (await db_session.execute(select(ProfileHandle))).scalars().all()
    assert handles == []
