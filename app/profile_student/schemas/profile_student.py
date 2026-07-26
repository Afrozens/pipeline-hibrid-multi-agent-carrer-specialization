from uuid import UUID
from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from app.core.schemas import PaginatedResponse
from app.profile_student_attribute.schema import (
    ProfileStudentAttributeCreate,
    ProfileStudentAttributeResponse,
)


class ProfileStudentBase(BaseModel):
    name: str = Field(..., description="Profile display name")
    source_type: str = Field(
        default="form",
        description="Profile origin: 'pdf' (uploaded CV) or 'form' (manual input)"
    )
    file_name: Optional[str] = Field(
        default=None,
        description="Original filename when source_type='pdf'"
    )
    status: str = Field(
        default="pending",
        description="Processing status: pending, incomplete, or complete"
    )


class ProfileStudentCreate(ProfileStudentBase):
    attributes: List[ProfileStudentAttributeCreate] = Field(
        ..., description="List of categorized attributes for this profile"
    )


class ProfileStudentResponse(ProfileStudentBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None
    attributes: List[ProfileStudentAttributeResponse] = []

    class Config:
        from_attributes = True


class ProfileStudentSimpleResponse(ProfileStudentBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None
    full_name: Optional[str] = None

    class Config:
        from_attributes = True


class ProfileStudentUploadResponse(BaseModel):
    profile: ProfileStudentResponse
    missing_fields: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="Map of category_name -> list of missing required keys"
    )
    message: str = Field(
        default="Profile created successfully.",
        description="Human-readable status message"
    )


class ProfileStudentValidationResponse(BaseModel):
    profile_id: UUID
    status: str
    missing_fields: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="Map of category_name -> list of missing required keys"
    )
    message: str = Field(
        default="Validation completed.",
        description="Human-readable validation summary"
    )


class ProfileStudentPaginatedResponse(PaginatedResponse[ProfileStudentSimpleResponse]):
    pass
