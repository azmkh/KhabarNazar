"""The analysis pipelines from the project diagram, and the evaluation step that receives their results.

Text  -> text pipeline -> text classification ------------------------------------------> evaluation
Image -> image pipeline -+-> OCR -> (usable text?) -> text classification -> image pair -> evaluation
                         +-> image analysis (AI-generated or real) -> Grad-CAM ---------> evaluation

OCR and image analysis are NOT alternatives. Every valid image is read by OCR *and* checked by the
AI-or-real detector, whose ResNet18 member also produces the Grad-CAM heatmap. OCR only decides
whether there is a news claim to classify; it never decides whether the picture is analysed.

The `branch` name records whether OCR text was classified: "image_pair" (usable text was found and
sent to the text pipeline) or "ai_or_real" (no usable text, so only the picture was analysed).

The evaluation step does NOT combine the outputs into one score. The verdict and the fake-news
risk come only from a text classification (typed text, or the text of an image pair). The
AI-or-real result and its Grad-CAM are reported on their own: an AI-generated picture does not make
a claim false, and a real photo does not make it true.
"""

from __future__ import annotations

import logging
from typing import Optional

from app.ai.image.ocr import has_usable_text, run_ocr
from app.ai.image.predict import analyze_image
from app.ai.text.explain import explain_text
from app.ai.text.predict import UNAVAILABLE_MODEL_VERSION, predict_text
from app.config import settings

logger = logging.getLogger(__name__)

BRANCH_TEXT = "text"
BRANCH_IMAGE_PAIR = "image_pair"  # usable OCR text was classified; the picture was analysed too
BRANCH_AI_OR_REAL = "ai_or_real"  # no usable OCR text: only the picture was analysed
# Stored in image_submissions.manipulation_prediction by older versions, which skipped the detector
# for images with text. Kept so those rows are still recognised; new submissions never store it.
SKIPPED_HAS_TEXT = "Skipped: image has text"


def run_text_pipeline(text: str, language: Optional[str] = None) -> dict:
    """Classify text; explain it only when a real model produced the prediction."""
    classification = predict_text(text, language=language)
    explanation = (
        explain_text(text, language=language, prediction=classification)
        if not classification.get("is_stub") else None
    )
    return {"classification": classification, "explanation": explanation}


def _text_pipeline_failed(language: Optional[str]) -> dict:
    """A clearly marked unavailable classification when the text pipeline itself raised."""
    return {
        "classification": {
            "prediction": "Uncertain",
            "confidence": None,
            "fake_probability": None,
            "summary": "The text classifier failed on the extracted text. Check the backend log.",
            "model_version": UNAVAILABLE_MODEL_VERSION,
            "detected_language": language,
            "is_stub": True,
            "status": "unavailable",
            "input_truncated": False,
        },
        "explanation": None,
    }


def run_image_pipeline(image_path: str) -> dict:
    """Run OCR (and, with usable text, the text pipeline) AND the image analysis with Grad-CAM.

    Each part handles its own failure, so an OCR error never stops the image analysis and a
    detector or Grad-CAM error never discards the OCR text or its classification.
    """
    ocr = run_ocr(image_path)
    text = None
    if has_usable_text(ocr, settings.OCR_MIN_LETTERS, settings.OCR_MIN_CONFIDENCE):
        # Image pair: the same text pipeline as typed text, on the extracted text of this image.
        try:
            text = run_text_pipeline(ocr["text"], language=ocr.get("language"))
        except Exception:
            logger.exception("Text pipeline failed on OCR text")
            text = _text_pipeline_failed(ocr.get("language"))
    # Always analyse the original uploaded picture, whatever OCR found.
    image = analyze_image(image_path)
    return {
        "branch": BRANCH_IMAGE_PAIR if text is not None else BRANCH_AI_OR_REAL,
        "ocr": ocr,
        "text": text,
        "image": image,
    }


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
    """What OCR found and whether that text was checked as a news claim."""
    if ocr.get("is_stub"):
        return (f"{ocr.get('message') or 'OCR is unavailable.'} Any text in the image could not be read, "
                "so no news claim was checked.")
    if branch == BRANCH_IMAGE_PAIR:
        return (f"OCR read text from the image (average confidence {ocr['confidence']:.2f}), "
                "so the text was checked as the news claim.")
    if ocr.get("text"):
        return "OCR found only a little or unclear text, too little to check as a news claim."
    return "OCR found no readable text, so no news claim was checked."


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
