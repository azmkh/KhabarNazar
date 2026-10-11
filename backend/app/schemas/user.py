from typing import Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.schemas.common import UTCDateTime


class UserBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=100, description="User's full name")
    email: EmailStr = Field(..., description="User's unique email address")


class UserCreate(UserBase):
    password: str = Field(..., min_length=6, max_length=72, description="User's plaintext password")

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            raise ValueError("Name must contain at least 2 non-whitespace characters")
        return value

    @field_validator("password")
    @classmethod
    def password_fits_bcrypt(cls, value: str) -> str:
        # bcrypt only accepts 72 bytes; Urdu characters take 2 bytes each in UTF-8.
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password is too long (maximum 72 bytes)")
        return value


class UserResponse(UserBase):
    id: int
    role: str
    created_at: UTCDateTime
    updated_at: Optional[UTCDateTime] = None

    model_config = ConfigDict(from_attributes=True)
