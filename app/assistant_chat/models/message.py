from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.assistant_chat.enums.message_role import MessageRole


class AssistantMessage(Base):
    __tablename__ = "assistant_messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assistant_conversations.id"), nullable=False
    )
    role: Mapped[MessageRole] = mapped_column(
        String(50), nullable=False
    )
    content: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    tool_call_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    tool_name: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    tool_arguments: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )
    tool_result: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )
    tokens_used: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    model: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )
    message_metadata: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )
    sequence: Mapped[int] = mapped_column(
        Integer, nullable=False
    )

    conversation: Mapped["AssistantConversation"] = relationship(
        "AssistantConversation", back_populates="messages"
    )
