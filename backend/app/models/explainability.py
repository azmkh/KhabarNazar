from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class Explainability(Base):
    __tablename__ = "explainability"

    id = Column(Integer, primary_key=True, index=True)
    submission_id = Column(Integer, ForeignKey("submissions.id", ondelete="CASCADE"), nullable=False, unique=True)
    # Highlighted words stored as JSON string: [{"word": "...", "score": 0.88}, ...]
    highlighted_words = Column(Text, nullable=True)
    # Path to heatmap image (for image submissions), relative to uploads/
    heatmap_path = Column(String(512), nullable=True)
    explanation_summary = Column(Text, nullable=True)
    model_version = Column(String(50), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    submission = relationship("Submission", back_populates="explainability")

    def __repr__(self) -> str:
        return f"<Explainability id={self.id} submission_id={self.submission_id}>"
