from fastapi import APIRouter, Depends

from app.core.dependencies import verify_api_key
from app.profile_student.router import router as profile_student_router
from app.assistant_chat.router import router as assistant_chat_router

api_router = APIRouter()


@api_router.get("/health")
async def health():
    return {"status": "ok"}


protected_router = APIRouter(dependencies=[Depends(verify_api_key)])
protected_router.include_router(profile_student_router, prefix="/api/v1")
protected_router.include_router(assistant_chat_router, prefix="/api/v1")

api_router.include_router(protected_router)
