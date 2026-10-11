from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class ImageSubmission(Base):
    __tablename__ = "image_submissions"

    id = Column(Integer, primary_key=True, index=True)
    submission_id = Column(Integer, ForeignKey("submissions.id", ondelete="CASCADE"), nullable=False, unique=True)
    image_path = Column(String(512), nullable=False)        # Path relative to uploads/
    original_filename = Column(String(255), nullable=True)
    mime_type = Column(String(100), nullable=True)
    file_size_bytes = Column(Integer, nullable=True)
    ocr_text = Column(Text, nullable=True)                  # Text extracted via OCR
    ocr_confidence = Column(Float, nullable=True)           # 0.0 – 1.0
    detected_language = Column(String(50), nullable=True)   # Language of OCR text
    text_prediction = Column(String(50), nullable=True)     # Extracted-claim model result, if available
    text_confidence = Column(Float, nullable=True)          # Extracted-claim model confidence, if available
    image_score = Column(Float, nullable=True)              # Visual/authenticity score 0.0 – 1.0
    manipulation_prediction = Column(String(50), nullable=True)  # 'Likely Authentic', 'Possibly Manipulated', etc.
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    submission = relationship("Submission", back_populates="image_submission")

    def __repr__(self) -> str:
        return f"<ImageSubmission id={self.id} manipulation={self.manipulation_prediction}>"
