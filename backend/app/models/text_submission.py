from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class TextSubmission(Base):
    __tablename__ = "text_submissions"

    id = Column(Integer, primary_key=True, index=True)
    submission_id = Column(Integer, ForeignKey("submissions.id", ondelete="CASCADE"), nullable=False, unique=True)
    input_text = Column(Text, nullable=False)
    detected_language = Column(String(50), nullable=True)   # 'urdu', 'roman_urdu', 'english', 'mixed'
    text_prediction = Column(String(50), nullable=True)     # 'Fake', 'Real', 'Uncertain', 'Pending'
    text_confidence = Column(Float, nullable=True)          # 0.0 – 1.0
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    submission = relationship("Submission", back_populates="text_submission")

    def __repr__(self) -> str:
        return f"<TextSubmission id={self.id} prediction={self.text_prediction}>"
