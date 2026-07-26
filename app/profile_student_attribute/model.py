from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ProfileStudentAttribute(Base):
    __tablename__ = "profile_student_attributes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profile_student.id"), nullable=False
    )
    category_name: Mapped[str] = mapped_column(
        String(255), nullable=False,
        comment="Attribute category (e.g. 'personal_info', 'education')"
    )
    key: Mapped[str] = mapped_column(
        String(255), nullable=False,
        comment="Field name (e.g. 'full_name', 'years_of_experience')"
    )
    value: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="Field value in plain text format"
    )

    profile: Mapped["ProfileStudent"] = relationship(
        "ProfileStudent", back_populates="attributes"
    )
