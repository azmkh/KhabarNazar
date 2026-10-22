"""Text classifier interface with an explicit unavailable-model fallback.

Three models, chosen per input:

| Input                                    | Model                                     |
|------------------------------------------|-------------------------------------------|
| Urdu script, up to LONG_TEXT_WORDS words | XLM-R trained on Urdu news items          |
| Urdu script, longer (full articles)      | TF-IDF + Logistic Regression (FIRE 2021)  |
| Latin letters (Roman Urdu)               | XLM-R trained on the KhabarNazar Roman Urdu dataset |

If a model is missing, the next available one is used; with no model at all the
result is a clearly marked "Uncertain" stub.
"""

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

from app.ai.text import xlmr
from app.ai.text.language_detection import detect_language
from app.ai.text.preprocess import normalize_text

logger = logging.getLogger(__name__)

DEFAULT_MODEL_PATH = (
    Path(__file__).resolve().parents[4] / "text_module" / "urdu" / "models" / "tfidf_long_articles.joblib"
)
# Stored in Explainability.model_version so clients can tell real results from placeholders.
UNAVAILABLE_MODEL_VERSION = "text-model-unavailable"
# The Urdu XLM-R model was trained on short news items (~20-35 words); longer
# Urdu inputs go to the TF-IDF model, which did better on full articles.
LONG_TEXT_WORDS = int(os.environ.get("KHABARNAZAR_LONG_TEXT_WORDS", "150"))
DEFAULT_LABEL_MAP = {"1": "Fake", "0": "Real"}


def _model_path() -> Path:
    return Path(os.environ.get("KHABARNAZAR_TEXT_MODEL_PATH", str(DEFAULT_MODEL_PATH))).expanduser()


@lru_cache(maxsize=2)
def _load_model(path: str, modified_at: int):
    # Include mtime in the cache key so replacing a trained model activates it.
    del modified_at
    artifact = joblib.load(path)
    if not isinstance(artifact, dict):  # a bare scikit-learn pipeline saved from the notebook
        artifact = {"model": artifact, "label_map": DEFAULT_LABEL_MAP}
    return artifact


def load_text_model() -> tuple[Optional[dict], Optional[str]]:
    """Return the TF-IDF (model bundle, None) or (None, reason it is unavailable)."""
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


def script_of(text: str, language: Optional[str] = None) -> str:
    """'urdu' for Arabic-script input, otherwise 'roman' (Latin letters)."""
    if language == "urdu":
        return "urdu"
    if language in {"roman_urdu", "english"}:
        return "roman"
    letters = [character for character in text if character.isalpha()]
    urdu = sum("؀" <= character <= "ۿ" for character in letters)
    return "urdu" if letters and urdu / len(letters) >= 0.5 else "roman"


def choose_model(text: str, language: Optional[str] = None) -> tuple[str, object, Optional[str]]:
    """Pick the model for this input.

    Returns (kind, model, script) with kind "xlmr" or "tfidf", or
    ("unavailable", reason, script).
    """
    script = script_of(text, language)
    is_long = len(text.split()) > LONG_TEXT_WORDS
    bundle, tfidf_reason = load_text_model()

    if script == "urdu" and is_long and bundle is not None:
        return "tfidf", bundle, script
    if xlmr.is_configured(script):
        classifier, reason = xlmr.get_classifier(script)
        if classifier is not None:
            return "xlmr", classifier, script
        logger.warning("Falling back from XLM-R: %s", reason)
    if bundle is not None:
        return "tfidf", bundle, script
    return "unavailable", tfidf_reason, script


def _unavailable(reason: str) -> dict:
    return {
        "prediction": "Uncertain",
        "confidence": None,
        "fake_probability": None,
        "summary": reason,
        "model_version": UNAVAILABLE_MODEL_VERSION,
        "is_stub": True,
    }


def tfidf_fake_probability(bundle: dict, text: str) -> tuple[float, str]:
    """(probability of Fake, model version) from the TF-IDF bundle."""
    classifier = bundle["model"]
    label_map = {str(key): value for key, value in bundle.get("label_map", DEFAULT_LABEL_MAP).items()}
    classes = [str(value) for value in classifier.classes_]
    probabilities = classifier.predict_proba([normalize_text(text)])[0]
    fake_index = next(index for index, value in enumerate(classes) if label_map[value] == "Fake")
    return float(probabilities[fake_index]), bundle.get("model_version", "text-tfidf-logreg")


def predict_text(text: str, language: Optional[str] = None) -> dict:
    """Run the matching classifier, or return a clearly marked unavailable result.

    - confidence: probability of the predicted label (how sure the model is).
    - fake_probability: probability of "Fake"; this, not confidence, is the risk.
    """
    kind, model, script = choose_model(text, language)
    if kind == "unavailable":
        return _unavailable(model)

    if kind == "xlmr":
        fake_probability = model.fake_probabilities([normalize_text(text)])[0]
        model_version = model.model_version
    else:
        fake_probability, model_version = tfidf_fake_probability(model, text)

    prediction = "Fake" if fake_probability >= 0.5 else "Real"
    confidence = fake_probability if prediction == "Fake" else 1 - fake_probability
    resolved_language = language or detect_language(text)
    return {
        "prediction": prediction,
        "confidence": round(float(confidence), 4),
        "fake_probability": round(float(fake_probability), 4),
        "summary": (
            f"The trained text classifier predicted {prediction.lower()} "
            f"for {resolved_language.replace('_', ' ')} text."
        ),
        "model_version": model_version,
        "is_stub": False,
    }
