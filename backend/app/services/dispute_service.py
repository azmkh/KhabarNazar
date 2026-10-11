from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.models.dispute import Dispute
from app.models.submission import Submission
from app.models.user import User
from app.schemas.dispute import DisputeCreate, DisputeReview


def _with_review_details(query):
    return query.options(
        joinedload(Dispute.submission).joinedload(Submission.text_submission),
        joinedload(Dispute.submission).joinedload(Submission.image_submission),
        joinedload(Dispute.submission).joinedload(Submission.explainability),
        joinedload(Dispute.user),
    )


def create_dispute(db: Session, user: User, dispute_in: DisputeCreate) -> Dispute:
    submission = db.query(Submission).filter(Submission.id == dispute_in.submission_id).first()
    if submission is None or submission.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found.")

    pending_dispute = (
        db.query(Dispute)
        .filter(
            Dispute.submission_id == submission.id,
            Dispute.user_id == user.id,
            Dispute.status == "pending",
        )
        .first()
    )
    if pending_dispute:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A pending dispute already exists for this submission.",
        )

    dispute = Dispute(
        submission_id=submission.id,
        user_id=user.id,
        justification=dispute_in.justification,
        evidence_link=dispute_in.evidence_link,
        status="pending",
    )
    db.add(dispute)
    db.commit()
    return _with_review_details(db.query(Dispute)).filter(Dispute.id == dispute.id).first()


def list_disputes(
    db: Session,
    current_user: User,
    dispute_status: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
) -> list[Dispute]:
    query = db.query(Dispute)
    if current_user.role != "admin":
        query = query.filter(Dispute.user_id == current_user.id)
    if dispute_status:
        query = query.filter(Dispute.status == dispute_status)
    return (
        _with_review_details(query)
        .order_by(Dispute.created_at.desc(), Dispute.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def get_dispute(db: Session, dispute_id: int, current_user: User) -> Dispute:
    query = db.query(Dispute).filter(Dispute.id == dispute_id)
    if current_user.role != "admin":
        query = query.filter(Dispute.user_id == current_user.id)
    dispute = _with_review_details(query).first()
    if dispute is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dispute not found.")
    return dispute


def review_dispute(db: Session, dispute_id: int, review: DisputeReview) -> Dispute:
    dispute = (
        _with_review_details(db.query(Dispute))
        .filter(Dispute.id == dispute_id)
        .first()
    )
    if dispute is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dispute not found.")
    if dispute.status != "pending":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This dispute has already been reviewed.")

    dispute.admin_decision = review.admin_decision
    dispute.admin_comment = review.admin_comment
    dispute.override_label = review.override_label
    dispute.status = "reviewed"
    dispute.reviewed_at = datetime.now(timezone.utc)

    dispute.submission.admin_comment = review.admin_comment
    if review.admin_decision == "override":
        dispute.submission.final_label = review.override_label
        dispute.submission.final_label_source = "Admin"

    db.commit()
    return _with_review_details(db.query(Dispute)).filter(Dispute.id == dispute.id).first()
