from uuid import UUID
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.assistant_chat.controllers.message_controller import (
    create_message,
    get_message,
    list_messages,
)
from app.assistant_chat.schemas.message import (
    AssistantMessageCreate,
    AssistantMessageResponse,
)

router = APIRouter()


@router.post("", response_model=AssistantMessageResponse, status_code=201)
async def post_message(
    data: AssistantMessageCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await create_message(db, data)


@router.get("/by-conversation/{conversation_id}", response_model=list[AssistantMessageResponse])
async def get_messages_by_conversation(
    conversation_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await list_messages(db, conversation_id)


@router.get("/{message_id}", response_model=AssistantMessageResponse)
async def get_one_message(
    message_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await get_message(db, message_id)
