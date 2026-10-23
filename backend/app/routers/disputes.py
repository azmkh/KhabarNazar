from typing import List, Optional

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.dispute import DisputeCreate, DisputeResponse, DisputeReview
from app.services.dispute_service import count_disputes, create_dispute, get_dispute, list_disputes, review_dispute
from app.utils.dependencies import TOTAL_COUNT_HEADER, get_current_admin, get_current_user


router = APIRouter(prefix="/disputes", tags=["Disputes"])


@router.post("", response_model=DisputeResponse, status_code=status.HTTP_201_CREATED)
def submit_dispute(
    dispute_in: DisputeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Submit a dispute for one of the current user's submissions."""
    return create_dispute(db, current_user, dispute_in)


@router.get("", response_model=List[DisputeResponse])
def get_disputes(
    response: Response,
    dispute_status: Optional[str] = Query(default=None, alias="status", pattern="^(pending|reviewed|closed)$"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    mine: bool = Query(default=False, description="Admins: only disputes filed by yourself"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Users see their disputes; admins see all disputes and can filter by status.

    The total number of matching disputes (across all pages) is in the
    X-Total-Count response header.
    """
    response.headers[TOTAL_COUNT_HEADER] = str(count_disputes(db, current_user, dispute_status, mine))
    return list_disputes(db, current_user, dispute_status, skip, limit, mine)


@router.get("/{dispute_id}", response_model=DisputeResponse)
def get_dispute_detail(
    dispute_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get one dispute; non-admin users can see only their own."""
    return get_dispute(db, dispute_id, current_user)


@router.patch("/{dispute_id}", response_model=DisputeResponse)
def patch_dispute(
    dispute_id: int,
    review: DisputeReview,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    """Record an admin decision. Overrides also update the submission's final label."""
    return review_dispute(db, dispute_id, review)
