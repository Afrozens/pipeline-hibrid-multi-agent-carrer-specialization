import logging
import uuid
from typing import Dict, List
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.assistant_chat.enums.message_role import MessageRole
from app.assistant_chat.models.conversation import AssistantConversation
from app.assistant_chat.schemas.message import AssistantMessageCreate, AssistantMessageResponse
from app.assistant_chat.services.message_service import create_message
from app.profile_student.constants.status import ProfileStudentStatus
from app.profile_student.models.model import ProfileStudent
from app.profile_student.utils import CriticalFieldValidator, unflatten_attributes
from app.generation.utils.attributes import unflatten_attributes as gen_unflatten

logger = logging.getLogger(__name__)
_validator = CriticalFieldValidator()


async def get_conversation_orm(
    db: AsyncSession, conversation_id: UUID
) -> AssistantConversation | None:
    stmt = (
        select(AssistantConversation)
        .where(AssistantConversation.id == conversation_id)
        .where(AssistantConversation.deleted_at.is_(None))
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_profile_orm(
    db: AsyncSession, profile_id: UUID
) -> ProfileStudent | None:
    stmt = (
        select(ProfileStudent)
        .where(ProfileStudent.id == profile_id)
        .where(ProfileStudent.deleted_at.is_(None))
        .options(selectinload(ProfileStudent.attributes))
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def create_and_link_profile(
    db: AsyncSession, conversation: AssistantConversation
) -> ProfileStudent:
    profile = ProfileStudent(
        name=f"{MessageRole.ASSISTANT}-{uuid.uuid4()}",
        source_type="form",
        status=ProfileStudentStatus.INCOMPLETE,
    )
    db.add(profile)
    await db.flush()
    await db.refresh(profile)
    conversation.profile_id = profile.id
    await db.flush()
    await db.commit()
    await db.refresh(profile, ["attributes"])
    logger.info(
        "CHAT_PROFILE_CREATED | conversation_id=%s | profile_id=%s",
        conversation.id,
        profile.id,
    )
    return profile


async def close_conversation_service(
    db: AsyncSession, conversation_id: UUID
) -> tuple[AssistantMessageResponse, UUID, str, Dict[str, List[str]]]:
    conversation = await get_conversation_orm(db, conversation_id)
    if not conversation:
        raise ValueError("Conversation not found")

    if not conversation.profile_id:
        raise ValueError("Conversation has no linked profile")

    profile = await get_profile_orm(db, conversation.profile_id)
    if not profile:
        raise ValueError("Linked profile not found")

    profile.status = ProfileStudentStatus.COMPLETE.value
    await db.commit()
    await db.refresh(profile)

    extracted = gen_unflatten(profile.attributes)
    collected = _validator.validate_extracted_fields(extracted)

    farewell = (
        "Thank you! Your career profile has been finalized and is now complete. "
        "A career advisor will review it shortly. If you have any questions, "
        "feel free to reach out. Have a great day!"
    )
    farewell_msg = await create_message(
        db,
        AssistantMessageCreate(
            conversation_id=conversation_id,
            role=MessageRole.ASSISTANT,
            content=farewell,
        ),
    )

    logger.info(
        "CLOSE_CONVERSATION_SERVICE_DONE | conversation_id=%s | profile_id=%s | status=%s",
        conversation_id,
        profile.id,
        profile.status,
    )

    return farewell_msg, profile.id, profile.status, collected
