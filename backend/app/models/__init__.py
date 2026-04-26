"""SQLAlchemy ORM models.

Every model module must be imported here so its table is registered on
`Base.metadata` for Alembic autogenerate to see it.
"""

from app.models.ai_call import AiCall
from app.models.fit import FitAssessment
from app.models.job import Job, JobSource, SearchQuery
from app.models.profile import Profile, ProfileHandle
from app.models.resume import Resume

__all__ = [
    "AiCall",
    "FitAssessment",
    "Job",
    "JobSource",
    "Profile",
    "ProfileHandle",
    "Resume",
    "SearchQuery",
]
