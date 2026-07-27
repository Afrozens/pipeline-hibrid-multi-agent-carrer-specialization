from uuid import UUID
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from app.assistant_chat.schemas.message import AssistantMessageResponse
from app.profile_student_attribute.schema import ProfileStudentAttributeResponse


class ChatStartRequest(BaseModel):
    user_id: Optional[UUID] = Field(default=None, description="Owner user UUID")


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="User message content")


class ChatResponse(BaseModel):
    assistant_message: AssistantMessageResponse = Field(
        ..., description="The assistant's reply message persisted in DB"
    )
    updated_attributes: List[ProfileStudentAttributeResponse] = Field(
        default_factory=list,
        description="New attributes that were extracted and saved to the profile",
    )
    current_category: str = Field(
        ..., description="The category currently being collected"
    )
    missing_fields: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="Map of category -> missing keys after this turn",
    )
    profile_status: str = Field(
        ..., description="Current profile status: pending | incomplete | complete"
    )
    profile_id: UUID = Field(..., description="Linked profile student ID")
