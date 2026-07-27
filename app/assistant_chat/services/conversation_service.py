from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.assistant_chat.enums.conversation_status import ConversationStatus
from app.assistant_chat.models.conversation import AssistantConversation
from app.assistant_chat.schemas.conversation import (
    AssistantConversationCreate,
    AssistantConversationResponse,
    AssistantConversationUpdate,
)


async def create_conversation(
    db: AsyncSession, data: AssistantConversationCreate
) -> AssistantConversationResponse:
    conversation = AssistantConversation(
        user_id=data.user_id,
        profile_id=data.profile_id,
        title=data.title,
        status=ConversationStatus.ACTIVE,
    )
    db.add(conversation)
    await db.flush()
    await db.refresh(conversation)
    return AssistantConversationResponse.model_validate(conversation)


async def list_conversations(
    db: AsyncSession,
    user_id: UUID | None = None,
    profile_id: UUID | None = None,
) -> list[AssistantConversationResponse]:
    stmt = (
        select(AssistantConversation)
        .where(AssistantConversation.deleted_at.is_(None))
        .order_by(AssistantConversation.updated_at.desc())
    )
    if user_id is not None:
        stmt = stmt.where(AssistantConversation.user_id == user_id)
    if profile_id is not None:
        stmt = stmt.where(AssistantConversation.profile_id == profile_id)
    result = await db.execute(stmt)
    conversations = result.scalars().all()
    return [AssistantConversationResponse.model_validate(c) for c in conversations]


async def get_conversation_by_id(
    db: AsyncSession, conversation_id: UUID
) -> AssistantConversationResponse | None:
    stmt = (
        select(AssistantConversation)
        .where(AssistantConversation.id == conversation_id)
        .where(AssistantConversation.deleted_at.is_(None))
    )
    result = await db.execute(stmt)
    conversation = result.scalar_one_or_none()
    if not conversation:
        return None
    return AssistantConversationResponse.model_validate(conversation)


async def update_conversation(
    db: AsyncSession,
    conversation_id: UUID,
    data: AssistantConversationUpdate,
) -> AssistantConversationResponse | None:
    stmt = (
        select(AssistantConversation)
        .where(AssistantConversation.id == conversation_id)
        .where(AssistantConversation.deleted_at.is_(None))
    )
    result = await db.execute(stmt)
    conversation = result.scalar_one_or_none()
    if not conversation:
        return None

    if data.title is not None:
        conversation.title = data.title
    if data.status is not None:
        conversation.status = data.status
    if data.context_summary is not None:
        conversation.context_summary = data.context_summary

    await db.flush()
    await db.refresh(conversation)
    return AssistantConversationResponse.model_validate(conversation)


async def soft_delete_conversation(
    db: AsyncSession, conversation_id: UUID
) -> bool:
    from datetime import datetime

    stmt = (
        select(AssistantConversation)
        .where(AssistantConversation.id == conversation_id)
        .where(AssistantConversation.deleted_at.is_(None))
    )
    result = await db.execute(stmt)
    conversation = result.scalar_one_or_none()
    if not conversation:
        return False
    conversation.deleted_at = datetime.now()
    conversation.status = ConversationStatus.CLOSED
    await db.flush()
    return True
