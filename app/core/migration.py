"""
Alembic must point here so that Base.metadata detects all tables.
Import all SQLAlchemy models below once they are created.
"""

from app.core.database import Base  # noqa: F401
