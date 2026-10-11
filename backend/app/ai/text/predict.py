"""Text classifier interface with an explicit unavailable-model fallback."""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

try:
    import joblib
except ImportError:  # Keep the API's explicit stub usable before ML deps are installed.
    joblib = None

from app.ai.text.language_detection import detect_language
from app.ai.text.preprocess import normalize_text

logger = logging.getLogger(__name__)

DEFAULT_MODEL_PATH = Path(__file__).resolve().parents[4] / "models" / "text" / "text_classifier.joblib"
# Stored in Explainability.model_version so clients can tell real results from placeholders.
UNAVAILABLE_MODEL_VERSION = "text-model-unavailable"


def _model_path() -> Path:
    return Path(os.environ.get("KHABARNAZAR_TEXT_MODEL_PATH", str(DEFAULT_MODEL_PATH))).expanduser()


@lru_cache(maxsize=2)
def _load_model(path: str, modified_at: int):
    # Include mtime in the cache key so replacing a trained model activates it.
    del modified_at
    return joblib.load(path)


def load_text_model() -> tuple[Optional[dict], Optional[str]]:
    """Return (model bundle, None) or (None, reason it is unavailable)."""
    model_path = _model_path()
    if not model_path.is_file():
        return None, "Text model not connected. Train it with the project dataset before using predictions."
    if joblib is None:
        return None, "Text model artifact exists, but joblib is not installed in the backend environment."
    try:
        return _load_model(str(model_path.resolve()), model_path.stat().st_mtime_ns), None
    except Exception:
        # e.g. scikit-learn missing or the artifact is corrupt / from an incompatible version.
        logger.exception("Could not load text model from %s", model_path)
        return None, "Text model artifact could not be loaded. Check the backend log and retrain if needed."


def _unavailable(reason: str) -> dict:
    return {
        "prediction": "Uncertain",
        "confidence": None,
        "fake_probability": None,
        "summary": reason,
        "model_version": UNAVAILABLE_MODEL_VERSION,
        "is_stub": True,
    }


def predict_text(text: str, language: Optional[str] = None) -> dict:
    """Run the trained classifier, or return a clearly marked unavailable result.

    - confidence: probability of the predicted label (how sure the model is).
    - fake_probability: probability of "Fake"; this, not confidence, is the risk.
    """
    bundle, reason = load_text_model()
    if bundle is None:
        return _unavailable(reason)

    classifier = bundle["model"]
    label_map = {str(key): value for key, value in bundle["label_map"].items()}
    classes = [str(value) for value in classifier.classes_]
    probabilities = classifier.predict_proba([normalize_text(text)])[0]
    best_index = int(probabilities.argmax())
    prediction = label_map[classes[best_index]]
    fake_index = next(index for index, value in enumerate(classes) if label_map[value] == "Fake")
    resolved_language = language or detect_language(text)
    return {
        "prediction": prediction,
        "confidence": round(float(probabilities[best_index]), 4),
        "fake_probability": round(float(probabilities[fake_index]), 4),
        "summary": (
            f"The trained text classifier predicted {prediction.lower()} "
            f"for {resolved_language.replace('_', ' ')} text."
        ),
        "model_version": bundle.get("model_version", "text-tfidf-logreg"),
        "is_stub": False,
    }
