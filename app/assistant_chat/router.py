from fastapi import APIRouter

from app.assistant_chat.routes.conversation import router as conversation_routes
from app.assistant_chat.routes.message import router as message_routes
from app.assistant_chat.routes.chat import router as chat_routes

router = APIRouter()
router.include_router(conversation_routes, prefix="/conversations", tags=["assistant-chat"])
router.include_router(message_routes, prefix="/messages", tags=["assistant-chat"])
router.include_router(chat_routes, tags=["assistant-chat"])
