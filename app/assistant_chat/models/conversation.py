from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.assistant_chat.enums.conversation_status import ConversationStatus


class AssistantConversation(Base):
    __tablename__ = "assistant_conversations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profile_student.id"), nullable=True
    )
    profile_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profile_student.id"), nullable=True
    )
    title: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    status: Mapped[ConversationStatus] = mapped_column(
        String(50),
        default=ConversationStatus.ACTIVE.value,
    )
    context_summary: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )

    messages: Mapped[list["AssistantMessage"]] = relationship(
        "AssistantMessage",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="AssistantMessage.sequence",
    )
