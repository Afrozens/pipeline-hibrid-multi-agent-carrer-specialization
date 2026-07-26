import logging
import uuid
from typing import Any, Dict, List
from uuid import UUID
from datetime import datetime

from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.utils.pdf import remove_temp_file, save_upload_to_temp
from app.profile_student.constants.source import SOURCE_FORM, SOURCE_PDF
from app.profile_student.schemas.profile_student import (
    ProfileStudentPaginatedResponse,
    ProfileStudentResponse,
    ProfileStudentSimpleResponse,
    ProfileStudentUploadResponse,
    ProfileStudentValidationResponse,
)
from app.profile_student.models.model import ProfileStudent
from app.profile_student.services.profile_student_service import (
    add_attributes_to_profile,
    create_profile_with_attributes,
    get_all_profiles_by_status,
    get_all_profiles_paginated,
    get_profile_by_id,
    get_profile_by_id_simple,
    upsert_attributes_to_profile,
    validate_profile,
)
from app.profile_student.utils import (
    CriticalFieldValidator,
    extract_pdf_markdown,
)
from app.profile_student_attribute.model import ProfileStudentAttribute
from app.profile_student_attribute.schema import (
    ProfileStudentAttributeBulkUpdate,
    ProfileStudentAttributeCreate,
    ProfileStudentAttributeResponse,
)

logger = logging.getLogger(__name__)
settings = get_settings()
_validator = CriticalFieldValidator()


async def upload_profile_student(
    db: AsyncSession,
    file: UploadFile,
    filename: str,
    source_type: str,
) -> ProfileStudentUploadResponse:
    logger.info("UPLOAD_START | filename=%s", filename)

    temp_path = await save_upload_to_temp(file)
    logger.info("UPLOAD_TEMP_SAVED | path=%s | filename=%s", temp_path, filename)

    try:
        with open(temp_path, "rb") as f:
            content = f.read()

        if not content:
            logger.warning("UPLOAD_EMPTY | filename=%s", filename)
            raise HTTPException(status_code=400, detail="Empty file uploaded.")

        extracted: Dict[str, Dict[str, Any]] = {}
        md_text = extract_pdf_markdown(content)
        if md_text:
            extracted = {"cv_raw": {"markdown": md_text}}

        missing = _validator.validate_extracted_fields(extracted)
        missing_count = sum(len(value) for value in missing.values())
        logger.info(
            "UPLOAD_VALIDATED | filename=%s | missing_categories=%d | missing_keys=%d",
            filename, len(missing), missing_count,
        )

        result = await create_profile_with_attributes(
            db=db,
            name=filename,
            source_type=source_type,
            file_name=filename,
            s3_file_key=None,
            extracted_fields=extracted,
            missing_fields=missing,
        )

        logger.info(
            "UPLOAD_COMPLETE | profile_id=%s | status=%s | missing_keys=%d",
            result.profile.id, result.profile.status, missing_count,
        )

        return result
    finally:
        remove_temp_file(temp_path)


async def get_profile_student(
    db: AsyncSession, profile_id: str
) -> ProfileStudentResponse:
    profile = await get_profile_by_id(db, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile student not found")
    return profile


async def get_all_profile_students(
    db: AsyncSession,
    *,
    page: int,
    limit: int,
    filter: str | None,
) -> ProfileStudentPaginatedResponse:
    result = await get_all_profiles_paginated(
        db=db,
        page=page,
        limit=limit,
        filter=filter,
    )
    return ProfileStudentPaginatedResponse.model_validate(result)


async def validate_profile_student(
    db: AsyncSession, profile_id: UUID
) -> ProfileStudentValidationResponse:
    result = await validate_profile(db, profile_id)
    if not result:
        raise HTTPException(status_code=404, detail="Profile student not found")
    return result


async def get_all_profile_students_by_status(
    db: AsyncSession,
    *,
    status: str,
) -> List[ProfileStudentSimpleResponse]:
    return await get_all_profiles_by_status(db=db, status=status)


async def update_profile_attributes(
    db: AsyncSession,
    profile_id: str,
    attributes: List[ProfileStudentAttributeBulkUpdate],
) -> List[ProfileStudentAttributeResponse]:
    profile = await get_profile_by_id(db, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile student not found")

    upserted = await upsert_attributes_to_profile(db, profile_id, attributes)

    validation_result = await validate_profile(db, profile_id)
    if validation_result:
        missing_count = sum(len(value) for value in validation_result.missing_fields.values())
        logger.info(
            "UPDATE_ATTRIBUTES_STATUS | profile_id=%s | status=%s | missing_keys=%d",
            profile_id,
            validation_result.status,
            missing_count,
        )

    return upserted


async def create_form_profile_student(
    db: AsyncSession,
    name: str,
    attributes: List[ProfileStudentAttributeCreate],
) -> ProfileStudentUploadResponse:
    extracted: Dict[str, Dict[str, Any]] = {}
    for attr in attributes:
        category = extracted.setdefault(attr.category_name, {})
        keys = attr.key.split(".")
        current = category
        for k in keys[:-1]:
            current = current.setdefault(k, {})
        current[keys[-1]] = attr.value

    missing = _validator.validate_extracted_fields(extracted)
    missing_count = sum(len(value) for value in missing.values())
    logger.info(
        "FORM_PROFILE_VALIDATED | name=%s | missing_categories=%d | missing_keys=%d",
        name, len(missing), missing_count,
    )

    result = await create_profile_with_attributes(
        db=db,
        name=name,
        source_type=SOURCE_FORM,
        file_name=None,
        s3_file_key=None,
        extracted_fields=extracted,
        missing_fields=missing,
    )

    logger.info(
        "FORM_PROFILE_COMPLETE | profile_id=%s | status=%s | missing_keys=%d",
        result.profile.id, result.profile.status, missing_count,
    )

    return result


async def create_empty_form_profile(
    db: AsyncSession,
) -> ProfileStudentResponse:
    profile = ProfileStudent(
        name=f"assistant-{uuid.uuid4()}",
        source_type=SOURCE_FORM,
        status="incomplete",
    )
    db.add(profile)
    await db.flush()
    await db.refresh(profile)

    result = await db.execute(
        select(ProfileStudent)
        .where(ProfileStudent.id == profile.id)
        .options(selectinload(ProfileStudent.attributes))
    )
    profile = result.scalar_one()

    return ProfileStudentResponse.model_validate(profile)


async def soft_delete_profile_student(
    db: AsyncSession,
    profile_id: UUID,
) -> bool:
    result = await db.execute(
        select(ProfileStudent)
        .where(ProfileStudent.id == profile_id)
        .where(ProfileStudent.deleted_at.is_(None))
    )
    profile = result.scalar_one_or_none()
    if not profile:
        return False

    now = datetime.now()
    profile.deleted_at = now

    attr_result = await db.execute(
        select(ProfileStudentAttribute)
        .where(ProfileStudentAttribute.profile_id == profile_id)
        .where(ProfileStudentAttribute.deleted_at.is_(None))
    )
    for attr in attr_result.scalars().all():
        attr.deleted_at = now

    await db.flush()
    return True
