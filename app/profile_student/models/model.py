from __future__ import annotations

import uuid

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.profile_student.constants.status import ProfileStudentStatus


class ProfileStudent(Base):
    __tablename__ = "profile_student"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(
        String(512), nullable=False,
        comment="Profile display name"
    )
    source_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default="form",
        comment="Profile origin: 'pdf' (uploaded CV) or 'form' (manual input)"
    )
    file_name: Mapped[str | None] = mapped_column(
        String(512), nullable=True,
        comment="Original filename when source_type='pdf'"
    )
    s3_file_key: Mapped[str | None] = mapped_column(
        String(512), nullable=True,
        comment="S3 object key for the uploaded PDF"
    )
    status: Mapped[ProfileStudentStatus] = mapped_column(
        String(50),
        default=ProfileStudentStatus.PENDING.value,
        comment="Processing status: pending, incomplete, or complete"
    )

    attributes: Mapped[list["ProfileStudentAttribute"]] = relationship(
        "ProfileStudentAttribute",
        back_populates="profile",
        cascade="all, delete-orphan",
    )

    @property
    def full_name(self) -> str | None:
        from app.profile_student_attribute.utils import decrypt_if_sensitive

        for attr in self.attributes:
            if attr.key == "full_name" and attr.deleted_at is None:
                return decrypt_if_sensitive(attr.key, attr.value)
        return None
