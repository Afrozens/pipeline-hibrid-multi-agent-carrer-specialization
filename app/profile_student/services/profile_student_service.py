from typing import Any, Dict, List
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.profile_student.models.model import ProfileStudent, ProfileStudentStatus
from app.profile_student.schemas.profile_student import (
    ProfileStudentResponse,
    ProfileStudentSimpleResponse,
    ProfileStudentUploadResponse,
    ProfileStudentValidationResponse,
)
from app.profile_student.utils import CriticalFieldValidator
from app.profile_student_attribute.model import ProfileStudentAttribute
from app.profile_student_attribute.schema import (
    ProfileStudentAttributeBulkUpdate,
    ProfileStudentAttributeCreate,
    ProfileStudentAttributeResponse,
)
from app.profile_student_attribute.utils import decrypt_if_sensitive
from app.profile_student.utils import flatten_category, unflatten_attributes

_validator = CriticalFieldValidator()


async def get_profile_by_id(
    db: AsyncSession, profile_id: UUID
) -> ProfileStudentResponse | None:
    result = await db.execute(
        select(ProfileStudent)
        .where(
            ProfileStudent.id == profile_id,
            ProfileStudent.deleted_at.is_(None),
        )
        .options(selectinload(ProfileStudent.attributes))
    )
    profile = result.scalar_one_or_none()
    if not profile:
        return None
    return ProfileStudentResponse.model_validate(profile)


async def get_profile_by_id_simple(
    db: AsyncSession, profile_id: UUID
) -> ProfileStudentSimpleResponse | None:
    result = await db.execute(
        select(ProfileStudent)
        .where(
            ProfileStudent.id == profile_id,
            ProfileStudent.deleted_at.is_(None),
        )
        .options(selectinload(ProfileStudent.attributes))
    )
    profile = result.scalar_one_or_none()
    if not profile:
        return None
    return ProfileStudentSimpleResponse.model_validate(profile)


async def get_all_profiles_paginated(
    db: AsyncSession,
    *,
    page: int,
    limit: int,
    filter: str | None,
) -> dict:
    stmt = (
        select(ProfileStudent)
        .where(ProfileStudent.deleted_at.is_(None))
        .options(selectinload(ProfileStudent.attributes))
    )
    count_stmt = select(func.count(ProfileStudent.id)).where(
        ProfileStudent.deleted_at.is_(None)
    )

    if filter and filter.lower() != "null":
        try:
            status_enum = ProfileStudentStatus(filter)
            stmt = stmt.where(ProfileStudent.status == status_enum.value)
            count_stmt = count_stmt.where(ProfileStudent.status == status_enum.value)
        except ValueError:
            pass

    total_result = await db.execute(count_stmt)
    total_records = total_result.scalar_one()

    offset = (page - 1) * limit
    stmt = stmt.order_by(ProfileStudent.created_at.desc()).offset(offset).limit(limit)

    result = await db.execute(stmt)
    profiles = result.scalars().all()

    total_pages = (total_records + limit - 1) // limit if limit > 0 else 0

    return {
        "page_number": page,
        "page_size": limit,
        "total_pages": total_pages,
        "total_record": total_records,
        "data": [ProfileStudentSimpleResponse.model_validate(p) for p in profiles],
    }


async def validate_profile(
    db: AsyncSession, profile_id: UUID
) -> ProfileStudentValidationResponse | None:
    result = await db.execute(
        select(ProfileStudent)
        .where(
            ProfileStudent.id == profile_id,
            ProfileStudent.deleted_at.is_(None),
        )
        .options(selectinload(ProfileStudent.attributes))
    )
    profile = result.scalar_one_or_none()
    if not profile:
        return None

    extracted = unflatten_attributes(profile.attributes)
    missing = _validator.validate_extracted_fields(extracted)

    new_status = (
        ProfileStudentStatus.COMPLETE.value
        if not missing
        else ProfileStudentStatus.INCOMPLETE.value
    )
    if profile.status != new_status:
        profile.status = new_status
        await db.commit()
        await db.refresh(profile)

    if missing:
        parts = [
            f"{cat}: {', '.join(keys)}"
            for cat, keys in missing.items()
        ]
        message = (
            "Profile is incomplete. Missing critical fields: "
            + "; ".join(parts)
        )
    else:
        message = "Profile is complete. All critical fields are present."

    return ProfileStudentValidationResponse(
        profile_id=profile.id,
        status=profile.status,
        missing_fields=missing,
        message=message,
    )


async def create_profile_with_attributes(
    db: AsyncSession,
    name: str,
    source_type: str,
    file_name: str | None,
    extracted_fields: Dict[str, Dict[str, Any]],
    missing_fields: Dict[str, List[str]],
    s3_file_key: str | None = None,
) -> ProfileStudentUploadResponse:
    status = (
        ProfileStudentStatus.COMPLETE.value
        if not missing_fields
        else ProfileStudentStatus.INCOMPLETE.value
    )

    profile = ProfileStudent(
        name=name,
        source_type=source_type,
        file_name=file_name,
        s3_file_key=s3_file_key,
        status=status,
    )
    db.add(profile)
    await db.flush()

    attributes_to_create: List[ProfileStudentAttributeCreate] = []
    for category_name, fields in extracted_fields.items():
        if isinstance(fields, dict):
            for cat, key, value in flatten_category(category_name, fields):
                attributes_to_create.append(
                    ProfileStudentAttributeCreate(
                        category_name=cat,
                        key=key,
                        value=str(value) if value is not None else None,
                    )
                )

    for attr_create in attributes_to_create:
        attr = ProfileStudentAttribute(
            profile_id=profile.id,
            category_name=attr_create.category_name,
            key=attr_create.key,
            value=attr_create.value,
        )
        db.add(attr)

    await db.commit()
    await db.refresh(profile)

    if missing_fields:
        parts = [
            f"{cat}: {', '.join(keys)}"
            for cat, keys in missing_fields.items()
        ]
        message = (
            "Profile created, but some critical fields are missing: "
            + "; ".join(parts)
        )
    else:
        message = "Profile created successfully with all critical fields present."

    result = await db.execute(
        select(ProfileStudent)
        .where(ProfileStudent.id == profile.id)
        .options(selectinload(ProfileStudent.attributes))
    )
    profile = result.scalar_one()

    return ProfileStudentUploadResponse(
        profile=ProfileStudentResponse.model_validate(profile),
        missing_fields=missing_fields,
        message=message,
    )


async def get_all_profiles_by_status(
    db: AsyncSession,
    *,
    status: str,
) -> List[ProfileStudentSimpleResponse]:
    stmt = (
        select(ProfileStudent)
        .where(
            ProfileStudent.deleted_at.is_(None),
            ProfileStudent.status == status,
        )
        .options(selectinload(ProfileStudent.attributes))
        .order_by(ProfileStudent.created_at.desc())
    )

    result = await db.execute(stmt)
    profiles = result.scalars().all()

    return [
        ProfileStudentSimpleResponse.model_validate(profile)
        for profile in profiles
    ]


async def add_attributes_to_profile(
    db: AsyncSession,
    profile_id: UUID,
    attributes: List[ProfileStudentAttributeCreate],
) -> List[ProfileStudentAttributeResponse]:
    if not attributes:
        return []

    stmt = select(ProfileStudentAttribute).where(
        ProfileStudentAttribute.profile_id == profile_id,
        ProfileStudentAttribute.deleted_at.is_(None),
    )
    existing_rows = (await db.execute(stmt)).scalars().all()

    existing_by_key: Dict[tuple[str, str], ProfileStudentAttribute] = {}
    for row in existing_rows:
        lookup = (row.category_name, row.key)
        current = existing_by_key.get(lookup)
        if current is None or row.updated_at > current.updated_at:
            existing_by_key[lookup] = row

    result_orm: List[ProfileStudentAttribute] = []
    for attr_create in attributes:
        lookup = (attr_create.category_name, attr_create.key)
        existing = existing_by_key.get(lookup)

        if existing is None:
            attr = ProfileStudentAttribute(
                profile_id=profile_id,
                category_name=attr_create.category_name,
                key=attr_create.key,
                value=attr_create.value,
            )
            db.add(attr)
            existing_by_key[lookup] = attr
            result_orm.append(attr)
            continue

        existing_plain = decrypt_if_sensitive(existing.key, existing.value)
        incoming_plain = decrypt_if_sensitive(attr_create.key, attr_create.value)
        if existing_plain == incoming_plain:
            continue

        existing.value = attr_create.value
        result_orm.append(existing)

    await db.flush()

    for attr in result_orm:
        await db.refresh(attr)

    return [ProfileStudentAttributeResponse.model_validate(attr) for attr in result_orm]


async def upsert_attributes_to_profile(
    db: AsyncSession,
    profile_id: UUID,
    attributes: List[ProfileStudentAttributeBulkUpdate],
) -> List[ProfileStudentAttributeResponse]:
    from sqlalchemy import select as sa_select

    result_orm: List[ProfileStudentAttribute] = []

    for attr_dto in attributes:
        if attr_dto.id:
            stmt = sa_select(ProfileStudentAttribute).where(
                ProfileStudentAttribute.id == attr_dto.id,
                ProfileStudentAttribute.profile_id == profile_id,
                ProfileStudentAttribute.deleted_at.is_(None),
            )
            attr = (await db.execute(stmt)).scalar_one_or_none()
            if attr:
                attr.value = attr_dto.value
                result_orm.append(attr)
            else:
                attr = ProfileStudentAttribute(
                    profile_id=profile_id,
                    category_name=attr_dto.category_name,
                    key=attr_dto.key,
                    value=attr_dto.value,
                )
                db.add(attr)
                result_orm.append(attr)
        else:
            attr = ProfileStudentAttribute(
                profile_id=profile_id,
                category_name=attr_dto.category_name,
                key=attr_dto.key,
                value=attr_dto.value,
            )
            db.add(attr)
            result_orm.append(attr)

    await db.flush()

    for attr in result_orm:
        await db.refresh(attr)

    return [ProfileStudentAttributeResponse.model_validate(attr) for attr in result_orm]
