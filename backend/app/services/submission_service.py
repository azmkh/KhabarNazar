from pathlib import Path
import json
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload, selectinload

from app.ai.image.explain import explain_image
from app.ai.pipeline import (
    BRANCH_IMAGE_PAIR,
    evaluate,
    ocr_summary,
    run_image_pipeline,
    run_text_pipeline,
)
from app.ai.text.language_detection import detect_language
from app.config import settings
from app.models.dispute import Dispute
from app.models.explainability import Explainability
from app.models.image_submission import ImageSubmission
from app.models.submission import Submission
from app.models.text_submission import TextSubmission
from app.models.user import User


def _highlighted_words_json(explanation: Optional[dict]) -> Optional[str]:
    if explanation and explanation["highlighted_words"]:
        return json.dumps(explanation["highlighted_words"], ensure_ascii=False)
    return None


def create_text_submission(db: Session, user_id: int, input_text: str) -> Submission:
    """
    Creates a text submission record, runs the text pipeline and the evaluation
    step, and stores all results to the database.
    """
    language = detect_language(input_text)
    text = run_text_pipeline(input_text, language=language)
    ai_result, text_explanation = text["classification"], text["explanation"]
    evaluation = evaluate("text", text)

    submission = Submission(
        user_id=user_id,
        submission_type="text",
        detected_language=language,
        combined_risk_score=evaluation["combined_risk_score"],
        final_label=evaluation["final_label"],
        final_label_source="AI",
    )
    db.add(submission)
    db.flush()  # Get submission.id before committing

    db.add(TextSubmission(
        submission_id=submission.id,
        input_text=input_text,
        detected_language=language,
        text_prediction=ai_result.get("prediction"),
        text_confidence=ai_result.get("confidence"),
    ))
    db.add(Explainability(
        submission_id=submission.id,
        highlighted_words=_highlighted_words_json(text_explanation),
        explanation_summary=(text_explanation["summary"] if text_explanation else ai_result.get("summary")),
        model_version=ai_result["model_version"],
    ))

    db.commit()
    return get_submission_by_id(db, submission_id=submission.id, user_id=user_id)


def create_image_submission(
    db: Session,
    user_id: int,
    image_path: str,
    original_filename: str,
    mime_type: str,
    file_size_bytes: int,
) -> Submission:
    """
    Runs the image pipeline: OCR decides between the image-pair branch (extracted
    text classified by the text pipeline) and the AI-generated vs real branch.
    Both are stored; only the text classification sets the verdict and risk.
    """
    abs_image_path = str(Path(settings.UPLOAD_DIR).resolve() / image_path)
    result = run_image_pipeline(abs_image_path)
    branch, ocr_result, img_result = result["branch"], result["ocr"], result["image"]
    text_ai = result["text"]["classification"] if result["text"] else None
    text_explanation = result["text"]["explanation"] if result["text"] else None
    evaluation = evaluate(branch, result["text"])

    submission = Submission(
        user_id=user_id,
        submission_type="image",
        detected_language=ocr_result.get("language"),
        combined_risk_score=evaluation["combined_risk_score"],
        final_label=evaluation["final_label"],
        final_label_source="AI",
    )
    db.add(submission)
    db.flush()

    db.add(ImageSubmission(
        submission_id=submission.id,
        image_path=image_path,
        original_filename=original_filename,
        mime_type=mime_type,
        file_size_bytes=file_size_bytes,
        ocr_text=ocr_result.get("text"),
        ocr_confidence=ocr_result.get("confidence"),
        detected_language=ocr_result.get("language"),
        text_prediction=(text_ai.get("prediction") if text_ai else None),
        text_confidence=(text_ai.get("confidence") if text_ai else None),
        image_score=img_result.get("image_score"),
        manipulation_prediction=img_result.get("manipulation_prediction"),
    ))

    # A heatmap is rendered only when the image detector supplied a Grad-CAM map.
    heatmap_relative_path = None
    heatmap_output_path = None
    if img_result.get("attribution_map") is not None:
        heatmap_relative_path = f"explanations/{submission.id}_heatmap.png"
        heatmap_output_path = Path(settings.UPLOAD_DIR).resolve() / heatmap_relative_path
    visual_explanation = explain_image(
        abs_image_path,
        attribution_map=img_result.get("attribution_map"),
        output_path=heatmap_output_path,
    )

    # Summarize the branch taken and each result; nothing is inferred beyond what a model returned.
    explanation_parts = [ocr_summary(ocr_result, branch)]
    if branch == BRANCH_IMAGE_PAIR:
        if text_ai and not text_ai.get("is_stub"):
            explanation_parts.append(text_explanation["summary"] if text_explanation else text_ai["summary"])
        else:
            explanation_parts.append(f"The extracted text could not be classified: {text_ai['summary']}")
    else:
        if img_result.get("summary"):
            explanation_parts.append(img_result["summary"])
        explanation_parts.append("No news claim was checked, so there is no fake-news verdict for this image.")
        if visual_explanation.get("heatmap_path"):
            explanation_parts.append(
                "The heatmap shows where the detector's ResNet18 member looked; it does not show edits."
            )

    if branch == BRANCH_IMAGE_PAIR:
        model_version = f"img-pair:{text_ai['model_version']}" if text_ai else "img-pair"
    else:
        model_version = img_result.get("model_version") or "image-model-unavailable"
    db.add(Explainability(
        submission_id=submission.id,
        highlighted_words=_highlighted_words_json(text_explanation),
        heatmap_path=heatmap_relative_path if visual_explanation.get("heatmap_path") else None,
        explanation_summary=" ".join(explanation_parts),
        model_version=model_version[:50],
    ))

    db.commit()
    return get_submission_by_id(db, submission_id=submission.id, user_id=user_id)


def get_submission_by_id(db: Session, submission_id: int, user_id: Optional[int]) -> Submission:
    """Fetches a single submission by ID. Pass user_id to enforce ownership,
    or None for administrator access."""
    query = (
        db.query(Submission)
        .options(
            joinedload(Submission.text_submission),
            joinedload(Submission.image_submission),
            joinedload(Submission.explainability),
        )
        .filter(Submission.id == submission_id)
    )
    if user_id is not None:
        query = query.filter(Submission.user_id == user_id)
    sub = query.first()
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Submission {submission_id} not found.",
        )
    return sub


def get_user_submissions(
    db: Session,
    user_id: int,
    skip: int = 0,
    limit: int = 50,
) -> List[Submission]:
    """Returns a paginated list of submissions for the given user, newest first."""
    return (
        db.query(Submission)
        .options(
            joinedload(Submission.text_submission),
            joinedload(Submission.image_submission),
            selectinload(Submission.disputes),
        )
        .filter(Submission.user_id == user_id)
        # id breaks ties between rows saved in the same instant, so pages never overlap or skip.
        .order_by(Submission.created_at.desc(), Submission.id.desc())
        .offset(skip)
        .limit(min(limit, 100))
        .all()
    )


def count_user_submissions(db: Session, user_id: int) -> int:
    return db.query(func.count(Submission.id)).filter(Submission.user_id == user_id).scalar() or 0


def get_all_submissions(db: Session, skip: int = 0, limit: int = 50) -> List[Submission]:
    """Return paginated submissions for the protected administrator console."""
    return (
        db.query(Submission)
        .options(
            joinedload(Submission.user),
            joinedload(Submission.text_submission),
            joinedload(Submission.image_submission),
            joinedload(Submission.explainability),
            selectinload(Submission.disputes),
        )
        .order_by(Submission.created_at.desc(), Submission.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def count_all_submissions(db: Session) -> int:
    return db.query(func.count(Submission.id)).scalar() or 0


def get_admin_stats(db: Session) -> dict:
    """Totals for the admin dashboard, counted in the database (not from one page of rows)."""
    by_label = dict(db.query(Submission.final_label, func.count(Submission.id)).group_by(Submission.final_label).all())
    by_type = dict(db.query(Submission.submission_type, func.count(Submission.id)).group_by(Submission.submission_type).all())
    dispute_status = dict(db.query(Dispute.status, func.count(Dispute.id)).group_by(Dispute.status).all())
    return {
        "users": db.query(func.count(User.id)).scalar() or 0,
        "submissions": sum(by_label.values()),
        "submissions_by_label": by_label,
        "submissions_by_type": by_type,
        "admin_overrides": db.query(func.count(Submission.id)).filter(Submission.final_label_source == "Admin").scalar() or 0,
        "disputes": {
            "total": sum(dispute_status.values()),
            "pending": dispute_status.get("pending", 0),
            "reviewed": sum(count for status, count in dispute_status.items() if status != "pending"),
        },
    }
