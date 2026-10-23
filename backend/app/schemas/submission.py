from app.schemas.common import UTCDateTime
from typing import List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

from app.ai.image.ai_detector import LABEL_AI_GENERATED, LABEL_REAL
from app.ai.image.predict import NOT_ANALYZED
from app.ai.pipeline import BRANCH_AI_OR_REAL, BRANCH_IMAGE_PAIR, SKIPPED_HAS_TEXT


# ─── Text Submission ──────────────────────────────────────────────────────────

class TextSubmissionResponse(BaseModel):
    id: int
    input_text: str
    detected_language: Optional[str] = None
    text_prediction: Optional[str] = None
    text_confidence: Optional[float] = None
    created_at: UTCDateTime

    @computed_field
    @property
    def processing_status(self) -> Literal["completed", "unavailable"]:
        """A null score means no compatible model produced a classification."""
        return "completed" if self.text_confidence is not None else "unavailable"

    model_config = ConfigDict(from_attributes=True)


# ─── Image Submission ─────────────────────────────────────────────────────────

class ImageSubmissionResponse(BaseModel):
    id: int
    image_path: str
    original_filename: Optional[str] = None
    mime_type: Optional[str] = None
    file_size_bytes: Optional[int] = None
    ocr_text: Optional[str] = None
    ocr_confidence: Optional[float] = None
    detected_language: Optional[str] = None
    text_prediction: Optional[str] = None
    text_confidence: Optional[float] = None
    image_score: Optional[float] = None  # probability the picture is AI-generated (ai_or_real branch)
    manipulation_prediction: Optional[str] = None
    created_at: UTCDateTime

    model_config = ConfigDict(from_attributes=True)

    @computed_field
    @property
    def analysis_branch(self) -> Optional[str]:
        """'image_pair' (text in the image was classified), 'ai_or_real' (the picture was checked),
        or None for images analysed before the pipeline had two branches."""
        if self.manipulation_prediction == SKIPPED_HAS_TEXT:
            return BRANCH_IMAGE_PAIR
        if self.manipulation_prediction in (LABEL_AI_GENERATED, LABEL_REAL, NOT_ANALYZED):
            return BRANCH_AI_OR_REAL
        return None


# ─── Explainability ───────────────────────────────────────────────────────────

class ExplainabilityResponse(BaseModel):
    id: int
    highlighted_words: Optional[str] = None  # JSON string
    heatmap_path: Optional[str] = None
    explanation_summary: Optional[str] = None
    model_version: Optional[str] = None
    created_at: UTCDateTime

    model_config = ConfigDict(from_attributes=True)


# ─── Submission (full) ────────────────────────────────────────────────────────

class SubmissionResponse(BaseModel):
    id: int
    user_id: int
    submission_type: str
    detected_language: Optional[str] = None
    is_news: Optional[bool] = None  # None = not evaluated (no news classifier connected)
    news_confidence: Optional[float] = None
    combined_risk_score: Optional[float] = None
    final_label: str
    final_label_source: str
    admin_comment: Optional[str] = None
    created_at: UTCDateTime

    text_submission: Optional[TextSubmissionResponse] = None
    image_submission: Optional[ImageSubmissionResponse] = None
    explainability: Optional[ExplainabilityResponse] = None

    model_config = ConfigDict(from_attributes=True)


# ─── Admin views ──────────────────────────────────────────────────────────────

class AdminSubmissionItem(SubmissionResponse):
    """A submission as listed to administrators: who sent it and its dispute status."""
    user_email: Optional[str] = None
    dispute_count: int = 0
    latest_dispute_id: Optional[int] = None
    latest_dispute_status: Optional[str] = None


class DisputeCounts(BaseModel):
    total: int
    pending: int
    reviewed: int


class AdminStats(BaseModel):
    users: int
    submissions: int
    submissions_by_label: dict[str, int]   # e.g. {"Fake": 3, "Real": 5, "Uncertain": 9}
    submissions_by_type: dict[str, int]    # e.g. {"text": 12, "image": 5}
    admin_overrides: int                   # submissions whose final label was set by an admin
    disputes: DisputeCounts


# ─── Submission list item (lighter) ──────────────────────────────────────────

class SubmissionListItem(BaseModel):
    id: int
    submission_type: str
    final_label: str
    final_label_source: str
    combined_risk_score: Optional[float] = None
    created_at: UTCDateTime
    # Brief preview fields
    text_preview: Optional[str] = None      # First 280 chars of input_text
    has_image: bool = False
    dispute_count: int = 0

    model_config = ConfigDict(from_attributes=True)


# ─── Text submission request ──────────────────────────────────────────────────

class TextSubmitRequest(BaseModel):
    text: str = Field(..., min_length=3, max_length=10_000, description="Urdu, Roman Urdu, or English news text to analyze")

    @field_validator("text")
    @classmethod
    def not_blank(cls, value: str) -> str:
        # min_length counts spaces; text that is only whitespace has nothing to classify.
        stripped = value.strip()
        if len(stripped) < 3:
            raise ValueError("Text must contain at least 3 non-space characters")
        return stripped
