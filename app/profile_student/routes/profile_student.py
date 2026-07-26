from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.profile_student.controllers.profile_student_controller import (
    create_empty_form_profile,
    create_form_profile_student,
    get_all_profile_students,
    get_all_profile_students_by_status,
    get_profile_student,
    soft_delete_profile_student,
    update_profile_attributes,
    upload_profile_student,
    validate_profile_student,
)
from app.profile_student.schemas.profile_student import (
    ProfileStudentCreate,
    ProfileStudentPaginatedResponse,
    ProfileStudentResponse,
    ProfileStudentSimpleResponse,
    ProfileStudentUploadResponse,
    ProfileStudentValidationResponse,
)
from app.profile_student.utils import UploadFileInfo, extract_upload_info
from app.profile_student_attribute.schema import (
    ProfileStudentAttributeBulkUpdate,
    ProfileStudentAttributeResponse,
)

router = APIRouter()


@router.post("/start", response_model=ProfileStudentResponse, status_code=201)
async def post_start(
    db: AsyncSession = Depends(get_db),
) -> ProfileStudentResponse:
    return await create_empty_form_profile(db)


@router.post("/form", response_model=ProfileStudentUploadResponse, status_code=201)
async def post_form(
    payload: ProfileStudentCreate,
    db: AsyncSession = Depends(get_db),
) -> ProfileStudentUploadResponse:
    return await create_form_profile_student(
        db=db,
        name=payload.name,
        attributes=payload.attributes,
    )


@router.post("/upload", response_model=ProfileStudentUploadResponse, status_code=201)
async def post_upload(
    db: AsyncSession = Depends(get_db),
    upload_info: UploadFileInfo = Depends(extract_upload_info),
) -> ProfileStudentUploadResponse:
    return await upload_profile_student(
        db=db,
        file=upload_info.file,
        filename=upload_info.filename,
        source_type=upload_info.source_type,
    )


@router.get("/all", status_code=status.HTTP_200_OK, response_model=ProfileStudentPaginatedResponse)
async def get_all(
    db: AsyncSession = Depends(get_db),
    page: int = 1,
    limit: int = 10,
    filter: str | None = Query(None, alias="filter"),
) -> ProfileStudentPaginatedResponse:
    return await get_all_profile_students(
        db=db,
        page=page,
        limit=limit,
        filter=filter,
    )


@router.get("/by-status/{status}", response_model=List[ProfileStudentSimpleResponse])
async def get_by_status(
    status: str,
    db: AsyncSession = Depends(get_db),
) -> List[ProfileStudentSimpleResponse]:
    return await get_all_profile_students_by_status(db=db, status=status)


@router.get("/{profile_id}", response_model=ProfileStudentResponse)
async def get_one(
    profile_id: str,
    db: AsyncSession = Depends(get_db),
) -> ProfileStudentResponse:
    return await get_profile_student(db, profile_id)


@router.get("/{profile_id}/validate", response_model=ProfileStudentValidationResponse)
async def get_validate(
    profile_id: str,
    db: AsyncSession = Depends(get_db),
) -> ProfileStudentValidationResponse:
    return await validate_profile_student(db, profile_id)


@router.put("/{profile_id}/attributes", response_model=List[ProfileStudentAttributeResponse])
async def put_attributes(
    profile_id: str,
    attributes: List[ProfileStudentAttributeBulkUpdate],
    db: AsyncSession = Depends(get_db),
) -> List[ProfileStudentAttributeResponse]:
    return await update_profile_attributes(db, profile_id, attributes)


@router.delete("/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_profile(
    profile_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    deleted = await soft_delete_profile_student(db, profile_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Profile student not found")
