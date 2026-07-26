"""
Alembic must point here so that Base.metadata detects all tables.
Import all SQLAlchemy models below once they are created.
"""

from app.core.database import Base  # noqa: F401

# Profile student models
from app.profile_student.models.model import ProfileStudent  # noqa: F401
from app.profile_student_attribute.model import ProfileStudentAttribute  # noqa: F401
