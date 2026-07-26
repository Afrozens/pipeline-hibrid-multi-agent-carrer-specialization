from fastapi import APIRouter

from app.profile_student.router import router as profile_student_router

api_router = APIRouter()


@api_router.get("/health")
async def health():
    return {"status": "ok"}


api_router.include_router(profile_student_router, prefix="/api/v1")
