from app.schemas.common import UTCDateTime
from typing import Literal, Optional
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.submission import SubmissionResponse
from app.schemas.user import UserResponse


class DisputeCreate(BaseModel):
    submission_id: int = Field(..., gt=0)
    justification: str = Field(..., min_length=10, max_length=5000)
    evidence_link: Optional[str] = Field(default=None, max_length=512)

    @field_validator("justification")
    @classmethod
    def strip_justification(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 10:
            raise ValueError("Justification must contain at least 10 non-whitespace characters")
        return value

    @field_validator("evidence_link")
    @classmethod
    def validate_evidence_link(cls, value: Optional[str]) -> Optional[str]:
        if value is None or not value.strip():
            return None
        value = value.strip()
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("Evidence link must be an HTTP or HTTPS URL")
        return value


class DisputeReview(BaseModel):
    admin_decision: Literal["uphold_ai", "override"]
    admin_comment: str = Field(..., min_length=3, max_length=5000)
    override_label: Optional[Literal["Fake", "Real", "Uncertain"]] = None

    @field_validator("admin_comment")
    @classmethod
    def strip_admin_comment(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 3:
            raise ValueError("Admin comment must contain at least 3 non-whitespace characters")
        return value

    @model_validator(mode="after")
    def validate_decision_fields(self):
        if self.admin_decision == "override" and self.override_label is None:
            raise ValueError("override_label is required when admin_decision is override")
        if self.admin_decision == "uphold_ai" and self.override_label is not None:
            raise ValueError("override_label must be omitted when upholding the AI result")
        return self


class DisputeResponse(BaseModel):
    id: int
    submission_id: int
    user_id: int
    justification: str
    evidence_link: Optional[str] = None
    status: str
    admin_decision: Optional[str] = None
    admin_comment: Optional[str] = None
    override_label: Optional[str] = None
    reviewed_at: Optional[UTCDateTime] = None
    created_at: UTCDateTime
    submission: Optional[SubmissionResponse] = None
    user: Optional[UserResponse] = None

    model_config = ConfigDict(from_attributes=True)
