from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.assistant_chat.schemas.conversation import (
    AssistantConversationCreate,
    AssistantConversationResponse,
    AssistantConversationUpdate,
)
from app.assistant_chat.services.conversation_service import (
    create_conversation as svc_create_conversation,
    get_conversation_by_id as svc_get_conversation_by_id,
    list_conversations as svc_list_conversations,
    soft_delete_conversation as svc_soft_delete_conversation,
    update_conversation as svc_update_conversation,
)


async def create_conversation(
    db: AsyncSession, data: AssistantConversationCreate
) -> AssistantConversationResponse:
    return await svc_create_conversation(db, data)


async def list_conversations(
    db: AsyncSession,
    user_id: UUID | None = None,
    profile_id: UUID | None = None,
) -> list[AssistantConversationResponse]:
    return await svc_list_conversations(db, user_id, profile_id)


async def get_conversation(
    db: AsyncSession, conversation_id: UUID
) -> AssistantConversationResponse:
    conversation = await svc_get_conversation_by_id(db, conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


async def update_conversation(
    db: AsyncSession,
    conversation_id: UUID,
    data: AssistantConversationUpdate,
) -> AssistantConversationResponse:
    conversation = await svc_update_conversation(db, conversation_id, data)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


async def delete_conversation(db: AsyncSession, conversation_id: UUID) -> None:
    deleted = await svc_soft_delete_conversation(db, conversation_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation not found")
