from uuid import UUID
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.assistant_chat.enums.conversation_status import ConversationStatus


class AssistantConversationCreate(BaseModel):
    user_id: UUID | None = None
    profile_id: UUID | None = None
    title: str | None = None


class AssistantConversationUpdate(BaseModel):
    title: str | None = None
    status: ConversationStatus | None = None
    context_summary: str | None = None


class AssistantConversationResponse(BaseModel):
    id: UUID
    user_id: UUID | None
    profile_id: UUID | None
    title: str | None
    status: str
    context_summary: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
