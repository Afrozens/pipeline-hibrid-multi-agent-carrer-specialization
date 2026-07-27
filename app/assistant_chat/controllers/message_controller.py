from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.assistant_chat.schemas.message import (
    AssistantMessageCreate,
    AssistantMessageResponse,
)
from app.assistant_chat.services.message_service import (
    create_message as svc_create_message,
    get_message_by_id as svc_get_message_by_id,
    list_messages_by_conversation as svc_list_messages_by_conversation,
)


async def create_message(
    db: AsyncSession, data: AssistantMessageCreate
) -> AssistantMessageResponse:
    return await svc_create_message(db, data)


async def list_messages(
    db: AsyncSession, conversation_id: UUID
) -> list[AssistantMessageResponse]:
    return await svc_list_messages_by_conversation(db, conversation_id)


async def get_message(
    db: AsyncSession, message_id: UUID
) -> AssistantMessageResponse:
    message = await svc_get_message_by_id(db, message_id)
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    return message
