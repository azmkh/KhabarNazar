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
from app.ai.image.preprocess import upright_image
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
EXPLANATION_UNAVAILABLE = "Detailed explanation is temporarily unavailable."


def run_text_pipeline(text: str, language: Optional[str] = None) -> dict:
    """Classify text; explain it only when a real model produced the prediction.

    The explanation is optional: if it cannot be built, the classification is still returned
    (use case 4-A) with a summary that says the detailed explanation is unavailable.
    """
    classification = predict_text(text, language=language)
    explanation = None
    if not classification.get("is_stub"):
        try:
            explanation = explain_text(text, language=language, prediction=classification)
        except Exception:
            logger.exception("Text explanation failed; returning the classification without it")
            explanation = {
                "highlighted_words": [],
                "summary": f"{classification['summary']} {EXPLANATION_UNAVAILABLE}",
                "is_stub": True,
            }
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
    # OCR and the detector both read the upright image, so the heatmap (drawn over the stored
    # upload, which OpenCV shows upright) lines up with what the detector analysed.
    with upright_image(image_path) as upright_path:
        ocr = run_ocr(upright_path)
        text = None
        if has_usable_text(ocr, settings.OCR_MIN_LETTERS, settings.OCR_MIN_CONFIDENCE):
            # Image pair: the same text pipeline as typed text, on the extracted text of this image.
            try:
                text = run_text_pipeline(ocr["text"], language=ocr.get("language"))
            except Exception:
                logger.exception("Text pipeline failed on OCR text")
                text = _text_pipeline_failed(ocr.get("language"))
        # Always analyse the uploaded picture, whatever OCR found.
        image = analyze_image(upright_path)
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


# Warm-up progress for /health: not_started (PRELOAD_MODELS off, models load on first use),
# loading, done (every loader ran; a model that failed is reported as not loaded), failed.
_warmup_state = "not_started"


def model_warmup() -> None:
    """Load every model once (startup, background thread); failures are logged by the loaders."""
    global _warmup_state
    from app.ai.image.ai_detector import load_detector
    from app.ai.image.ocr import load_ocr_reader
    from app.ai.text.xlmr import warmup_models

    _warmup_state = "loading"
    try:
        warmup_models()
        load_detector()
        try:
            load_ocr_reader()
        except Exception:
            logger.exception("EasyOCR warm-up failed; OCR will retry on first use")
        _warmup_state = "done"
    except Exception:
        _warmup_state = "failed"
        logger.exception("Model warm-up failed; models will load on first use")


def model_status() -> dict:
    """Which models are loaded in this process. Cheap: never loads or downloads anything.

    `ready` is true when every configured model is loaded; models whose files are not installed
    (e.g. no Roman Urdu weights) are listed as not configured and do not block readiness.
    """
    from app.ai.image import ai_detector, ocr
    from app.ai.text import xlmr

    models = {}
    for script, name in (("urdu", "urdu_text"), ("roman", "roman_urdu_text")):
        configured = xlmr.is_configured(script)
        models[name] = "loaded" if xlmr.is_loaded(script) else ("not_loaded" if configured else "not_configured")
    detector_files = all((ai_detector.model_dir() / f).is_file() for f in ai_detector.REQUIRED_FILES)
    models["image_detector"] = (
        "loaded" if ai_detector.is_loaded() else ("not_loaded" if detector_files else "not_configured")
    )
    models["ocr"] = "loaded" if ocr.is_loaded() else "not_loaded"
    ready = all(state != "not_loaded" for state in models.values())
    return {"ready": ready, "warmup": _warmup_state, "models": models}
