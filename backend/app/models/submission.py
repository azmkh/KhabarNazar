from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class Submission(Base):
    __tablename__ = "submissions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    submission_type = Column(String(20), nullable=False)  # 'text', 'image', 'both'
    detected_language = Column(String(50), nullable=True)  # 'urdu', 'roman_urdu', 'english', 'mixed'
    # None until a news/non-news classifier is connected; never assumed True.
    is_news = Column(Boolean, nullable=True)
    news_confidence = Column(Float, nullable=True)
    combined_risk_score = Column(Float, nullable=True)
    final_label = Column(String(50), default="Pending", nullable=False)  # 'Fake', 'Real', 'Uncertain', 'Pending'
    final_label_source = Column(String(50), default="AI", nullable=False)  # 'AI', 'Admin'
    admin_comment = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    user = relationship("User", back_populates="submissions")
    text_submission = relationship(
        "TextSubmission",
        back_populates="submission",
        uselist=False,
        cascade="all, delete-orphan",
    )
    image_submission = relationship(
        "ImageSubmission",
        back_populates="submission",
        uselist=False,
        cascade="all, delete-orphan",
    )
    explainability = relationship(
        "Explainability",
        back_populates="submission",
        uselist=False,
        cascade="all, delete-orphan",
    )
    disputes = relationship(
        "Dispute",
        back_populates="submission",
        cascade="all, delete-orphan",
        order_by="desc(Dispute.created_at)",
    )

    def __repr__(self) -> str:
        return f"<Submission id={self.id} type={self.submission_type} label={self.final_label}>"
