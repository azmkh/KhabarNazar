from app.schemas.common import UTCDateTime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


# ─── Text Submission ──────────────────────────────────────────────────────────

class TextSubmissionResponse(BaseModel):
    id: int
    input_text: str
    detected_language: Optional[str] = None
    text_prediction: Optional[str] = None
    text_confidence: Optional[float] = None
    created_at: UTCDateTime

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
    image_score: Optional[float] = None
    manipulation_prediction: Optional[str] = None
    created_at: UTCDateTime

    model_config = ConfigDict(from_attributes=True)


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
    text: str = Field(..., min_length=3, max_length=10_000, description="Urdu or Roman Urdu news text to analyze")
