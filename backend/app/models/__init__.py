"""SQLAlchemy ORM models.

Every model module must be imported here so its table is registered on
`Base.metadata` for Alembic autogenerate to see it.
"""

from app.models.ai_call import AiCall
from app.models.contact import Contact
from app.models.fit import FitAssessment
from app.models.job import Job, JobSource, SearchQuery
from app.models.outreach import OutreachDraft
from app.models.profile import Profile, ProfileHandle
from app.models.resume import Resume
from app.models.tailoring import TailoredArtifact, TailoringBrief
from app.models.trust import JobRepostHistory, TrustAssessment

__all__ = [
    "AiCall",
    "Contact",
    "FitAssessment",
    "Job",
    "JobRepostHistory",
    "JobSource",
    "OutreachDraft",
    "Profile",
    "ProfileHandle",
    "Resume",
    "SearchQuery",
    "TailoredArtifact",
    "TailoringBrief",
    "TrustAssessment",
]
