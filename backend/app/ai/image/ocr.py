"""OCR for Urdu/English text embedded in images (EasyOCR)."""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from pathlib import Path

from app.ai.text.language_detection import detect_language

logger = logging.getLogger(__name__)
SUPPORTED_OCR_LANGUAGES = ("ur", "en")


@lru_cache(maxsize=1)
def _get_ocr_reader(model_directory: str):
    """Load EasyOCR once per process; the first call may download its weights."""
    import easyocr

    Path(model_directory).mkdir(parents=True, exist_ok=True)
    return easyocr.Reader(
        list(SUPPORTED_OCR_LANGUAGES),
        gpu=False,
        model_storage_directory=model_directory,
        download_enabled=True,
    )


def run_ocr(image_path: str) -> dict:
    """Extract Urdu/English text with EasyOCR when installed and initialized."""
    model_directory = Path(
        os.environ.get(
            "KHABARNAZAR_OCR_MODEL_DIR",
            str(Path(__file__).resolve().parents[3] / ".cache" / "easyocr"),
        )
    ).expanduser()
    try:
        reader = _get_ocr_reader(str(model_directory.resolve()))
        detections = reader.readtext(image_path, detail=1, paragraph=False)
    except ImportError:
        return {
            "text": None,
            "confidence": None,
            "language": None,
            "is_stub": True,
            "status": "dependency_missing",
            "message": "EasyOCR is not installed. Install backend requirements to enable OCR.",
        }
    except Exception:
        logger.exception("EasyOCR could not initialize or process image %s", image_path)
        return {
            "text": None,
            "confidence": None,
            "language": None,
            "is_stub": True,
            "status": "unavailable",
            "message": "OCR could not process this image. Check the backend log for details.",
        }

    text_parts = [str(item[1]).strip() for item in detections if len(item) >= 3 and str(item[1]).strip()]
    confidences = [float(item[2]) for item in detections if len(item) >= 3 and str(item[1]).strip()]
    extracted_text = "\n".join(text_parts) or None
    confidence = sum(confidences) / len(confidences) if confidences else None
    return {
        "text": extracted_text,
        "confidence": round(confidence, 4) if confidence is not None else None,
        "language": detect_language(extracted_text) if extracted_text else None,
        "is_stub": False,
        "status": "completed" if extracted_text else "no_text_found",
        "message": None,
    }
