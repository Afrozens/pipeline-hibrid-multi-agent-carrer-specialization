from uuid import UUID
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.assistant_chat.controllers.conversation_controller import (
    create_conversation,
    delete_conversation,
    get_conversation,
    list_conversations,
    update_conversation,
)
from app.assistant_chat.schemas.conversation import (
    AssistantConversationCreate,
    AssistantConversationResponse,
    AssistantConversationUpdate,
)

router = APIRouter()


@router.post("", response_model=AssistantConversationResponse, status_code=201)
async def post_conversation(
    data: AssistantConversationCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await create_conversation(db, data)


@router.get("", response_model=list[AssistantConversationResponse])
async def get_conversations(
    db: Annotated[AsyncSession, Depends(get_db)],
    user_id: UUID | None = Query(None),
    profile_id: UUID | None = Query(None),
):
    return await list_conversations(db, user_id, profile_id)


@router.get("/{conversation_id}", response_model=AssistantConversationResponse)
async def get_one_conversation(
    conversation_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await get_conversation(db, conversation_id)


@router.patch("/{conversation_id}", response_model=AssistantConversationResponse)
async def patch_conversation(
    conversation_id: UUID,
    data: AssistantConversationUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await update_conversation(db, conversation_id, data)


@router.delete("/{conversation_id}", status_code=204)
async def del_conversation(
    conversation_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    await delete_conversation(db, conversation_id)
