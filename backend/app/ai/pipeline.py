"""The analysis pipelines from the project diagram, and the evaluation step that receives their results.

Text  -> text pipeline -> text classification ------------------------------> evaluation
Image -> image pipeline -> image with text    -> OCR -> text classification -> image pair -> evaluation
                        -> image with no text -> AI-generated or real ---------------------> evaluation

The two image branches are exclusive: an image with usable text is not sent to the AI-or-real
detector, and an image without usable text is never classified as a news claim.

The evaluation step does NOT combine the branches into one score. The verdict and the fake-news
risk come only from a text classification (typed text, or the text of an image pair). The
AI-or-real result is reported on its own: an AI-generated picture does not make a claim false,
and a real photo does not make it true.
"""

from __future__ import annotations

from typing import Optional

from app.ai.image.ocr import has_usable_text, run_ocr
from app.ai.image.predict import analyze_image
from app.ai.text.explain import explain_text
from app.ai.text.predict import predict_text
from app.config import settings

BRANCH_TEXT = "text"
BRANCH_IMAGE_PAIR = "image_pair"  # image with text: OCR text + its classification, tied to the image
BRANCH_AI_OR_REAL = "ai_or_real"  # image with no usable text: authenticity of the picture
# Stored in image_submissions.manipulation_prediction (VARCHAR(50)) when the detector is not run.
SKIPPED_HAS_TEXT = "Skipped: image has text"


def run_text_pipeline(text: str, language: Optional[str] = None) -> dict:
    """Classify text; explain it only when a real model produced the prediction."""
    classification = predict_text(text, language=language)
    explanation = (
        explain_text(text, language=language, prediction=classification)
        if not classification.get("is_stub") else None
    )
    return {"classification": classification, "explanation": explanation}


def run_image_pipeline(image_path: str) -> dict:
    """OCR first; route to the image-pair branch or the AI-or-real branch."""
    ocr = run_ocr(image_path)
    if has_usable_text(ocr, settings.OCR_MIN_LETTERS, settings.OCR_MIN_CONFIDENCE):
        # Image pair: the same text pipeline as typed text, on the extracted text of this image.
        text = run_text_pipeline(ocr["text"], language=ocr.get("language"))
        return {
            "branch": BRANCH_IMAGE_PAIR,
            "ocr": ocr,
            "text": text,
            "image": {
                "image_score": None,
                "manipulation_prediction": SKIPPED_HAS_TEXT,
                "is_stub": True,
                "status": "skipped",
                "summary": None,
                "attribution_map": None,
            },
        }
    return {"branch": BRANCH_AI_OR_REAL, "ocr": ocr, "text": None, "image": analyze_image(image_path)}


def evaluate(branch: str, text: Optional[dict] = None) -> dict:
    """Final label and fake-news risk for a submission, from its text classification only."""
    classification = (text or {}).get("classification")
    if branch == BRANCH_AI_OR_REAL or not classification or classification.get("is_stub"):
        return {"final_label": "Uncertain", "combined_risk_score": None}
    return {
        "final_label": classification["prediction"],
        "combined_risk_score": classification.get("fake_probability"),
    }


def ocr_summary(ocr: dict, branch: str) -> str:
    """What OCR found and how that decided the branch."""
    if ocr.get("is_stub"):
        return (f"{ocr.get('message') or 'OCR is unavailable.'} Any text in the image could not be read, "
                "so only the picture itself was checked.")
    if branch == BRANCH_IMAGE_PAIR:
        return (f"OCR read text from the image (average confidence {ocr['confidence']:.2f}), "
                "so the text was checked and the picture was not tested for AI generation.")
    if ocr.get("text"):
        return ("OCR found only a little or unclear text, too little to check as a news claim, "
                "so the picture itself was checked instead.")
    return "OCR found no readable text, so the picture itself was checked."


def model_warmup() -> None:
    """Load every model once (startup, background thread); failures are logged by the loaders."""
    from app.ai.image.ai_detector import load_detector
    from app.ai.image.ocr import load_ocr_reader
    from app.ai.text.xlmr import warmup_models

    warmup_models()
    load_detector()
    try:
        load_ocr_reader()
    except Exception:
        import logging

        logging.getLogger(__name__).exception("EasyOCR warm-up failed; OCR will retry on first use")
