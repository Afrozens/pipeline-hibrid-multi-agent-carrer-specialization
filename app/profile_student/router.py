from fastapi import APIRouter

from app.profile_student.routes.profile_student import router as profile_routes

router = APIRouter()
router.include_router(profile_routes, prefix="/profile-students", tags=["profile-students"])
