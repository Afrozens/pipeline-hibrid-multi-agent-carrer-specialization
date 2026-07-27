import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.assistant_chat.schemas.chat import ChatRequest, ChatResponse
from app.assistant_chat.controllers.chat_controller import chat, close_chat, start_chat, upload_chat_pdf

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/conversations/{conversation_id}/chat/start", response_model=ChatResponse)
async def start_chat_endpoint(
    conversation_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ChatResponse:
    return await start_chat(db, conversation_id)


@router.post("/conversations/{conversation_id}/chat", response_model=ChatResponse)
async def chat_endpoint(
    conversation_id: UUID,
    body: ChatRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ChatResponse:
    return await chat(db, conversation_id, body.message)


@router.post("/conversations/{conversation_id}/chat/upload-pdf", response_model=ChatResponse)
async def upload_chat_pdf_endpoint(
    conversation_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    file: UploadFile = File(..., description="PDF file to upload"),
) -> ChatResponse:
    return await upload_chat_pdf(db, conversation_id, file)


@router.post("/conversations/{conversation_id}/close", response_model=ChatResponse)
async def close_chat_endpoint(
    conversation_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ChatResponse:
    return await close_chat(db, conversation_id)
