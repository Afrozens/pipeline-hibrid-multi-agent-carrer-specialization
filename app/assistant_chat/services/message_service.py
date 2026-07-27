from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.assistant_chat.models.message import AssistantMessage
from app.assistant_chat.schemas.message import (
    AssistantMessageCreate,
    AssistantMessageResponse,
)


async def get_next_sequence(db: AsyncSession, conversation_id: UUID) -> int:
    stmt = select(func.max(AssistantMessage.sequence)).where(
        AssistantMessage.conversation_id == conversation_id
    )
    result = await db.execute(stmt)
    max_seq = result.scalar_one_or_none()
    return (max_seq or 0) + 1


async def create_message(
    db: AsyncSession, data: AssistantMessageCreate
) -> AssistantMessageResponse:
    sequence = await get_next_sequence(db, data.conversation_id)
    message = AssistantMessage(
        conversation_id=data.conversation_id,
        role=data.role,
        content=data.content,
        tool_call_id=data.tool_call_id,
        tool_name=data.tool_name,
        tool_arguments=data.tool_arguments,
        tool_result=data.tool_result,
        tokens_used=data.tokens_used,
        model=data.model,
        message_metadata=data.message_metadata,
        sequence=sequence,
    )
    db.add(message)
    await db.flush()
    await db.refresh(message)
    return AssistantMessageResponse.model_validate(message)


async def list_messages_by_conversation(
    db: AsyncSession, conversation_id: UUID
) -> list[AssistantMessageResponse]:
    stmt = (
        select(AssistantMessage)
        .where(AssistantMessage.conversation_id == conversation_id)
        .order_by(AssistantMessage.sequence.asc())
    )
    result = await db.execute(stmt)
    messages = result.scalars().all()
    return [AssistantMessageResponse.model_validate(m) for m in messages]


async def get_message_by_id(
    db: AsyncSession, message_id: UUID
) -> AssistantMessageResponse | None:
    stmt = select(AssistantMessage).where(AssistantMessage.id == message_id)
    result = await db.execute(stmt)
    message = result.scalar_one_or_none()
    if not message:
        return None
    return AssistantMessageResponse.model_validate(message)
