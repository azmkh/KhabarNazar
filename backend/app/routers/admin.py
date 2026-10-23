from typing import List

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.submission import AdminStats, AdminSubmissionItem, SubmissionResponse
from app.services.submission_service import count_all_submissions, get_admin_stats, get_all_submissions
from app.utils.dependencies import TOTAL_COUNT_HEADER, get_current_admin


router = APIRouter(prefix="/admin", tags=["Administration"])


@router.get("/submissions", response_model=List[AdminSubmissionItem])
def list_all_submissions(
    response: Response,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    """List all submissions for administrators, newest first, with the submitter
    and the latest dispute. The total across all pages is in X-Total-Count."""
    response.headers[TOTAL_COUNT_HEADER] = str(count_all_submissions(db))
    items = []
    for submission in get_all_submissions(db, skip, limit):
        latest = submission.disputes[0] if submission.disputes else None  # relationship is newest-first
        items.append(AdminSubmissionItem(
            **SubmissionResponse.model_validate(submission).model_dump(),
            user_email=submission.user.email if submission.user else None,
            dispute_count=len(submission.disputes),
            latest_dispute_id=latest.id if latest else None,
            latest_dispute_status=latest.status if latest else None,
        ))
    return items


@router.get("/stats", response_model=AdminStats)
def admin_stats(
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    """Totals for the admin dashboard, counted across the whole database."""
    return get_admin_stats(db)
