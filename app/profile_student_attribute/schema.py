from uuid import UUID
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, model_validator

from app.profile_student_attribute.utils import (
    decrypt_if_sensitive,
    encrypt_if_sensitive,
    is_already_encrypted,
    is_sensitive_key,
)


class ProfileStudentAttributeBase(BaseModel):
    category_name: str = Field(
        ..., description="Attribute category (e.g. 'personal_info', 'education')"
    )
    key: str = Field(
        ..., description="Field name (e.g. 'full_name', 'years_of_experience')"
    )
    value: Optional[str] = Field(
        default=None, description="Field value in plain text format"
    )


class ProfileStudentAttributeCreate(ProfileStudentAttributeBase):
    @model_validator(mode="after")
    def encrypt_sensitive_values(self):
        if is_sensitive_key(self.key) and self.value is not None:
            if not is_already_encrypted(self.value):
                self.value = encrypt_if_sensitive(self.key, self.value)
        return self


class ProfileStudentAttributeUpdate(BaseModel):
    category_name: Optional[str] = Field(
        default=None, description="Attribute category"
    )
    key: Optional[str] = Field(default=None, description="Field name")
    value: Optional[str] = Field(default=None, description="Field value")

    @model_validator(mode="after")
    def encrypt_sensitive_values(self):
        if self.key is not None and is_sensitive_key(self.key) and self.value is not None:
            if not is_already_encrypted(self.value):
                self.value = encrypt_if_sensitive(self.key, self.value)
        return self


class ProfileStudentAttributeBulkUpdate(BaseModel):
    id: Optional[UUID] = Field(
        default=None, description="Existing attribute UUID (omit to create)"
    )
    category_name: str = Field(..., description="Attribute category")
    key: str = Field(..., description="Field name")
    value: Optional[str] = Field(default=None, description="Field value")

    @model_validator(mode="after")
    def encrypt_sensitive_values(self):
        if is_sensitive_key(self.key) and self.value is not None:
            if not is_already_encrypted(self.value):
                self.value = encrypt_if_sensitive(self.key, self.value)
        return self


class ProfileStudentAttributeResponse(ProfileStudentAttributeBase):
    id: UUID
    profile_id: UUID
    deleted_at: Optional[datetime] = None

    @model_validator(mode="after")
    def decrypt_sensitive_values(self):
        if is_sensitive_key(self.key) and self.value is not None:
            if is_already_encrypted(self.value):
                self.value = decrypt_if_sensitive(self.key, self.value)
        return self

    class Config:
        from_attributes = True
