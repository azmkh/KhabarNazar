from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class Dispute(Base):
    __tablename__ = "disputes"

    id = Column(Integer, primary_key=True, index=True)
    submission_id = Column(Integer, ForeignKey("submissions.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    justification = Column(Text, nullable=False)
    evidence_link = Column(String(512), nullable=True)
    status = Column(String(20), default="pending", nullable=False)  # 'pending', 'reviewed', 'closed'
    admin_decision = Column(String(20), nullable=True)              # 'uphold_ai', 'override'
    admin_comment = Column(Text, nullable=True)
    override_label = Column(String(50), nullable=True)              # If overridden: 'Fake', 'Real', 'Uncertain'
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    submission = relationship("Submission", back_populates="disputes")
    user = relationship("User", back_populates="disputes")

    def __repr__(self) -> str:
        return f"<Dispute id={self.id} status={self.status}>"
