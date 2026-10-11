from pathlib import Path
import json
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload, selectinload

from app.ai.image.explain import explain_image
from app.ai.image.ocr import run_ocr
from app.ai.image.predict import analyze_image
from app.ai.text.explain import explain_text
from app.ai.text.language_detection import detect_language
from app.ai.text.predict import UNAVAILABLE_MODEL_VERSION, predict_text
from app.config import settings
from app.models.explainability import Explainability
from app.models.image_submission import ImageSubmission
from app.models.submission import Submission
from app.models.text_submission import TextSubmission


def _build_combined_risk(text_fake_probability: Optional[float], image_score: Optional[float]) -> Optional[float]:
    """
    Combines the text model's probability of "Fake" and the image manipulation
    score into one 0-1 risk score using the configured weights. Missing signals
    are left out (weights are renormalized); with no real signal the risk is None.
    """
    weighted = [
        (value, weight)
        for value, weight in (
            (text_fake_probability, settings.TEXT_RISK_WEIGHT),
            (image_score, settings.IMAGE_RISK_WEIGHT),
        )
        if value is not None and weight > 0
    ]
    if not weighted:
        return None
    total_weight = sum(weight for _, weight in weighted)
    return round(sum(value * weight for value, weight in weighted) / total_weight, 4)


def create_text_submission(db: Session, user_id: int, input_text: str) -> Submission:
    """
    Creates a text submission record, runs the (stub) AI pipeline,
    and stores all results to the database.
    """
    # 1. Language detection
    language = detect_language(input_text)

    # 2. AI text prediction (stub)
    ai_result = predict_text(input_text, language=language)

    # 3. Create parent Submission record
    submission = Submission(
        user_id=user_id,
        submission_type="text",
        detected_language=language,
        combined_risk_score=_build_combined_risk(ai_result["fake_probability"], None),
        final_label=ai_result["prediction"],
        final_label_source="AI",
    )
    db.add(submission)
    db.flush()  # Get submission.id before committing

    # 4. Create TextSubmission child record
    text_sub = TextSubmission(
        submission_id=submission.id,
        input_text=input_text,
        detected_language=language,
        text_prediction=ai_result.get("prediction"),
        text_confidence=ai_result.get("confidence"),
    )
    db.add(text_sub)

    # 5. Save model feature attributions when a trained text model is available.
    text_explanation = explain_text(input_text) if not ai_result.get("is_stub") else None
    explain = Explainability(
        submission_id=submission.id,
        highlighted_words=(
            json.dumps(text_explanation["highlighted_words"], ensure_ascii=False)
            if text_explanation and text_explanation["highlighted_words"]
            else None
        ),
        explanation_summary=(text_explanation["summary"] if text_explanation else ai_result.get("summary")),
        model_version=ai_result["model_version"],
    )
    db.add(explain)

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
    Runs OCR, analyzes extracted text when a trained text model is available,
    and stores visual authenticity as a separate signal.
    """
    abs_image_path = str(Path(settings.UPLOAD_DIR).resolve() / image_path)

    # 1. Extract embedded text. EasyOCR is loaded lazily on first use.
    ocr_result = run_ocr(abs_image_path)

    # 2. Image manipulation analysis stays separate from extracted news text.
    img_result = analyze_image(abs_image_path)

    # 3. Analyze OCR text with the Stage 5 model if a real artifact is configured.
    text_ai = None
    if ocr_result.get("text"):
        text_ai = predict_text(ocr_result["text"], language=ocr_result.get("language"))
    text_confidence = text_ai["confidence"] if text_ai else None
    text_fake_probability = text_ai["fake_probability"] if text_ai else None

    combined = _build_combined_risk(text_fake_probability, img_result.get("image_score"))
    final_label = text_ai.get("prediction", "Uncertain") if text_ai and not text_ai.get("is_stub") else "Uncertain"

    # 4. Create parent Submission record
    submission = Submission(
        user_id=user_id,
        submission_type="image",
        detected_language=ocr_result.get("language"),
        combined_risk_score=combined,
        final_label=final_label,
        final_label_source="AI",
    )
    db.add(submission)
    db.flush()

    # 5. Create ImageSubmission child record
    img_sub = ImageSubmission(
        submission_id=submission.id,
        image_path=image_path,
        original_filename=original_filename,
        mime_type=mime_type,
        file_size_bytes=file_size_bytes,
        ocr_text=ocr_result.get("text"),
        ocr_confidence=ocr_result.get("confidence"),
        detected_language=ocr_result.get("language"),
        text_prediction=(text_ai.get("prediction") if text_ai else None),
        text_confidence=text_confidence,
        image_score=img_result.get("image_score"),
        manipulation_prediction=img_result.get("manipulation_prediction"),
    )
    db.add(img_sub)

    # 6. Build text feature attribution and, only if a visual model provides one,
    # render its attribution array to an image heatmap.
    text_explanation = (
        explain_text(ocr_result["text"])
        if ocr_result.get("text") and text_ai and not text_ai.get("is_stub")
        else None
    )
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

    # 7. Summarize each signal and its availability; no claim is made from OCR alone.
    if ocr_result.get("text"):
        explanation_parts = [
            f"OCR extracted text with average confidence {ocr_result['confidence']:.2f}."
            if ocr_result.get("confidence") is not None
            else "OCR extracted text; confidence is unavailable."
        ]
        if text_ai and not text_ai.get("is_stub"):
            explanation_parts.append(text_explanation["summary"] if text_explanation else text_ai["summary"])
        else:
            explanation_parts.append("News claim classification is unavailable until a trained text model is connected.")
    elif ocr_result.get("status") == "no_text_found":
        explanation_parts = ["OCR completed but found no readable text."]
    else:
        explanation_parts = [ocr_result.get("message") or "OCR is unavailable."]
    if img_result.get("summary"):
        explanation_parts.append(img_result["summary"])
    explanation_parts.append(visual_explanation["summary"])
    explain = Explainability(
        submission_id=submission.id,
        highlighted_words=(
            json.dumps(text_explanation["highlighted_words"], ensure_ascii=False)
            if text_explanation and text_explanation["highlighted_words"]
            else None
        ),
        heatmap_path=heatmap_relative_path if visual_explanation.get("heatmap_path") else None,
        explanation_summary=" ".join(explanation_parts),
        model_version=(
            "easyocr+text+vision"
            if not ocr_result.get("is_stub") and text_explanation and visual_explanation.get("heatmap_path")
            else "easyocr+text"
            if not ocr_result.get("is_stub") and text_explanation
            else "easyocr-ur-en"
            if not ocr_result.get("is_stub")
            else "ocr-unavailable"
        ),
    )
    db.add(explain)

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
        .order_by(Submission.created_at.desc())
        .offset(skip)
        .limit(min(limit, 100))
        .all()
    )


def get_all_submissions(db: Session, skip: int = 0, limit: int = 50) -> List[Submission]:
    """Return paginated submissions for the protected administrator console."""
    return (
        db.query(Submission)
        .options(
            joinedload(Submission.user),
            joinedload(Submission.text_submission),
            joinedload(Submission.image_submission),
            joinedload(Submission.explainability),
        )
        .order_by(Submission.created_at.desc(), Submission.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
