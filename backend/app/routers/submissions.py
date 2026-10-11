from pathlib import Path
from typing import List
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.submission import Submission
from app.models.image_submission import ImageSubmission
from app.models.explainability import Explainability
from app.config import settings
from app.schemas.submission import SubmissionListItem, SubmissionResponse, TextSubmitRequest
from app.services.submission_service import (
    create_image_submission,
    create_text_submission,
    get_submission_by_id,
    get_user_submissions,
)
from app.utils.dependencies import get_current_user
from app.utils.upload import delete_upload, save_upload

router = APIRouter(prefix="/submissions", tags=["Submissions"])


@router.post(
    "/text",
    response_model=SubmissionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit Urdu or Roman Urdu text for analysis",
)
def submit_text(
    body: TextSubmitRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Accepts plaintext (Urdu or Roman Urdu), runs language detection and AI
    text analysis (stub), persists the result, and returns the full submission.
    """
    submission = create_text_submission(
        db=db,
        user_id=current_user.id,
        input_text=body.text,
    )
    return SubmissionResponse.model_validate(submission)


@router.post(
    "/image",
    response_model=SubmissionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit an image for OCR and authenticity analysis",
)
def submit_image(
    file: UploadFile = File(..., description="Image file (JPEG, PNG, or WEBP, max 10 MB)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Validates and stores the uploaded image, runs stub OCR and image analysis,
    persists the result, and returns the full submission record.
    """
    rel_path, original_name, file_size, mime_type = save_upload(file)
    try:
        submission = create_image_submission(
            db=db,
            user_id=current_user.id,
            image_path=rel_path,
            original_filename=original_name,
            mime_type=mime_type,
            file_size_bytes=file_size,
        )
    except Exception:
        # Do not leave an orphaned file on disk when analysis or saving fails.
        db.rollback()
        delete_upload(rel_path)
        raise
    return SubmissionResponse.model_validate(submission)


@router.get(
    "",
    response_model=List[SubmissionListItem],
    summary="List current user's submission history",
)
def list_submissions(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns a paginated list of the logged-in user's submissions,
    newest first, with lightweight preview fields.
    """
    submissions = get_user_submissions(db, user_id=current_user.id, skip=skip, limit=limit)
    items = []
    for sub in submissions:
        text_preview = None
        has_image = False
        if sub.text_submission:
            text_preview = sub.text_submission.input_text[:280]
        if sub.image_submission:
            has_image = True
        items.append(
            SubmissionListItem(
                id=sub.id,
                submission_type=sub.submission_type,
                final_label=sub.final_label,
                final_label_source=sub.final_label_source,
                combined_risk_score=sub.combined_risk_score,
                created_at=sub.created_at,
                text_preview=text_preview,
                has_image=has_image,
                dispute_count=len(sub.disputes) if sub.disputes else 0,
            )
        )
    return items


@router.get(
    "/{submission_id}",
    response_model=SubmissionResponse,
    summary="Get a specific submission by ID",
)
def get_submission(
    submission_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns the full details of a single submission including text/image
    analysis results and explainability data.
    Users can read only their own submissions; admins can read any submission.
    """
    owner_filter = None if current_user.role == "admin" else current_user.id
    submission = get_submission_by_id(db, submission_id=submission_id, user_id=owner_filter)
    return SubmissionResponse.model_validate(submission)


@router.get("/{submission_id}/image", summary="Read an uploaded image owned by the user or admin")
def get_submission_image(
    submission_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Stream an upload without exposing the upload directory publicly."""
    row = (
        db.query(ImageSubmission, Submission.user_id)
        .join(Submission, ImageSubmission.submission_id == Submission.id)
        .filter(Submission.id == submission_id)
        .first()
    )
    if row is None or (row[1] != current_user.id and current_user.role != "admin"):
        raise HTTPException(status_code=404, detail="Image not found.")

    upload_root = Path(settings.UPLOAD_DIR).resolve()
    image_file = (upload_root / row[0].image_path).resolve()
    try:
        image_file.relative_to(upload_root)
    except ValueError:
        raise HTTPException(status_code=404, detail="Image not found.")
    if not image_file.is_file():
        raise HTTPException(status_code=404, detail="Image file is no longer available.")
    return FileResponse(image_file, media_type=row[0].mime_type or "application/octet-stream")


@router.get("/{submission_id}/heatmap", summary="Read a model heatmap for an owned submission or admin")
def get_submission_heatmap(
    submission_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = (
        db.query(Explainability.heatmap_path, Submission.user_id)
        .join(Submission, Explainability.submission_id == Submission.id)
        .filter(Submission.id == submission_id)
        .first()
    )
    if row is None or not row[0] or (row[1] != current_user.id and current_user.role != "admin"):
        raise HTTPException(status_code=404, detail="Heatmap not found.")
    upload_root = Path(settings.UPLOAD_DIR).resolve()
    heatmap_file = (upload_root / row[0]).resolve()
    try:
        heatmap_file.relative_to(upload_root)
    except ValueError:
        raise HTTPException(status_code=404, detail="Heatmap not found.")
    if not heatmap_file.is_file():
        raise HTTPException(status_code=404, detail="Heatmap file is no longer available.")
    return FileResponse(heatmap_file, media_type="image/png")
