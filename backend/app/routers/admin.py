from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.submission import SubmissionResponse
from app.services.submission_service import get_all_submissions
from app.utils.dependencies import get_current_admin


router = APIRouter(prefix="/admin", tags=["Administration"])


@router.get("/submissions", response_model=List[SubmissionResponse])
def list_all_submissions(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    """List all submissions for administrators, newest first."""
    return get_all_submissions(db, skip, limit)
