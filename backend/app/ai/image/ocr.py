"""OCR for Urdu/English text embedded in images (EasyOCR)."""

from __future__ import annotations

import logging
import os
import threading
import warnings
from functools import lru_cache
from pathlib import Path

from app.ai.text.language_detection import detect_language

logger = logging.getLogger(__name__)
SUPPORTED_OCR_LANGUAGES = ("ur", "en")
_load_lock = threading.Lock()
_loaded = False


@lru_cache(maxsize=1)
def _get_ocr_reader(model_directory: str):
    """Load EasyOCR once per process; the first call may download its weights."""
    import easyocr

    Path(model_directory).mkdir(parents=True, exist_ok=True)
    with warnings.catch_warnings():
        # EasyOCR's CPU recognizer quantizes itself with a torch API that PyTorch now flags as
        # deprecated; it still works, and the warning is not actionable from this project.
        warnings.filterwarnings("ignore", message=r"torch\.quantize_per_tensor", category=UserWarning)
        return easyocr.Reader(
            list(SUPPORTED_OCR_LANGUAGES),
            gpu=False,
            model_storage_directory=model_directory,
            download_enabled=True,
        )


def load_ocr_reader():
    """Load (or return the already loaded) EasyOCR reader; used to warm up at startup."""
    global _loaded
    with _load_lock:  # two first requests at once must not load EasyOCR twice
        reader = _get_ocr_reader(str(_model_directory().resolve()))
        _loaded = True
        return reader


def is_loaded() -> bool:
    """True once EasyOCR is loaded in this process (does not load it)."""
    return _loaded


def _model_directory() -> Path:
    return Path(
        os.environ.get(
            "KHABARNAZAR_OCR_MODEL_DIR",
            str(Path(__file__).resolve().parents[3] / ".cache" / "easyocr"),
        )
    ).expanduser()


def has_usable_text(
    ocr_result: dict,
    min_letters: int,
    min_confidence: float,
    min_confidence_urdu: float | None = None,
) -> bool:
    """True when OCR found enough confidently read text to classify (the image-with-text branch).

    A few stray letters (a watermark, a logo) or a low-confidence read do not count. EasyOCR's
    Urdu recognizer reports much lower confidence than its Latin one for text it reads correctly,
    especially in Nastaliq, so Urdu-script text has its own cutoff (min_confidence_urdu).
    """
    text = ocr_result.get("text") or ""
    confidence = ocr_result.get("confidence")
    letters = sum(character.isalpha() for character in text)
    cutoff = min_confidence
    if min_confidence_urdu is not None and ocr_result.get("language") == "urdu":
        cutoff = min_confidence_urdu
    return letters >= min_letters and confidence is not None and confidence >= cutoff


def _is_arabic_script(text: str) -> bool:
    letters = [character for character in text if character.isalpha()]
    return bool(letters) and sum("؀" <= c <= "ۿ" or "ݐ" <= c <= "ݿ" or "ﭐ" <= c <= "﻿"
                                 for c in letters) * 2 > len(letters)


def _reading_order(detections: list) -> list[list[tuple[str, float]]]:
    """Group EasyOCR word boxes into lines, top to bottom, each in reading direction.

    EasyOCR returns boxes roughly top-to-bottom and left-to-right, which reverses the words of
    an Urdu line and, with tall overlapping Nastaliq lines, interleaves neighbouring lines.
    A box joins the current line when its vertical centre is within half a typical box height
    of the line's centre. Urdu lines are then read right to left, others left to right.
    """
    boxes = []
    for item in detections:
        if len(item) < 3 or not str(item[1]).strip():
            continue
        xs = [float(point[0]) for point in item[0]]
        ys = [float(point[1]) for point in item[0]]
        boxes.append({"text": str(item[1]).strip(), "conf": float(item[2]),
                      "x": (min(xs) + max(xs)) / 2, "y": (min(ys) + max(ys)) / 2, "h": max(ys) - min(ys)})
    if not boxes:
        return []
    heights = sorted(box["h"] for box in boxes)
    tolerance = max(heights[len(heights) // 2], 1.0) / 2
    lines: list[list[dict]] = []
    for box in sorted(boxes, key=lambda b: b["y"]):
        if lines and box["y"] - sum(b["y"] for b in lines[-1]) / len(lines[-1]) <= tolerance:
            lines[-1].append(box)
        else:
            lines.append([box])
    ordered = []
    for line in lines:
        right_to_left = _is_arabic_script(" ".join(b["text"] for b in line))
        line.sort(key=lambda b: b["x"], reverse=right_to_left)
        ordered.append([(b["text"], b["conf"]) for b in line])
    return ordered


def run_ocr(image_path: str) -> dict:
    """Extract Urdu/English text with EasyOCR when installed and initialized."""
    try:
        reader = load_ocr_reader()
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
        logger.exception("EasyOCR could not initialize or process the image")
        return {
            "text": None,
            "confidence": None,
            "language": None,
            "is_stub": True,
            "status": "unavailable",
            "message": "OCR could not process this image. Check the backend log for details.",
        }

    lines = _reading_order(detections)
    confidences = [confidence for line in lines for _, confidence in line]
    extracted_text = "\n".join(" ".join(text for text, _ in line) for line in lines) or None
    confidence = sum(confidences) / len(confidences) if confidences else None
    return {
        "text": extracted_text,
        "confidence": round(confidence, 4) if confidence is not None else None,
        "language": detect_language(extracted_text) if extracted_text else None,
        "is_stub": False,
        "status": "completed" if extracted_text else "no_text_found",
        "message": None,
    }
