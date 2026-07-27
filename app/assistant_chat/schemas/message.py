from uuid import UUID
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.assistant_chat.enums.message_role import MessageRole


class AssistantMessageCreate(BaseModel):
    conversation_id: UUID
    role: MessageRole
    content: str | None = None
    tool_call_id: str | None = None
    tool_name: str | None = None
    tool_arguments: dict | None = None
    tool_result: dict | None = None
    tokens_used: int | None = None
    model: str | None = None
    message_metadata: dict | None = None


class AssistantMessageResponse(BaseModel):
    id: UUID
    conversation_id: UUID
    role: str
    content: str | None
    tool_call_id: str | None
    tool_name: str | None
    tool_arguments: dict | None
    tool_result: dict | None
    tokens_used: int | None
    model: str | None
    message_metadata: dict | None
    sequence: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
