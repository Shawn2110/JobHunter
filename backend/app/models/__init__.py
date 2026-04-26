"""SQLAlchemy ORM models.

Every model module must be imported here so its table is registered on
`Base.metadata` for Alembic autogenerate to see it.
"""

from app.models.ai_call import AiCall

__all__ = ["AiCall"]
