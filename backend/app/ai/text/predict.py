"""Language-aware routing to the separately trained text models.

| Input                                    | Model                                         |
|------------------------------------------|-----------------------------------------------|
| Urdu script, up to LONG_TEXT_WORDS words | Urdu XLM-R (Hook and Bait, 64-token limit)    |
| Urdu script, longer (full articles)      | TF-IDF + Logistic Regression (FIRE 2021)      |
| Roman Urdu                               | Roman Urdu XLM-R (512-token limit)            |
| English, mixed script, unidentified      | none: an explicit Uncertain result            |

Long Urdu text falls back to the XLM-R model (truncated) when the TF-IDF file is missing.
"""

from __future__ import annotations

import logging
from typing import Optional

from app.ai.text import long_articles, xlmr
from app.ai.text.language_detection import detect_language
from app.config import settings

logger = logging.getLogger(__name__)
UNAVAILABLE_MODEL_VERSION = "text-model-unavailable"
# Word count above which Urdu text goes to the long-article model (KHABARNAZAR_LONG_TEXT_WORDS).
LONG_TEXT_WORDS = settings.LONG_TEXT_WORDS
SUPPORTED_TEXT_LANGUAGES = {"urdu", "roman_urdu"}


def _unavailable(language: str, reason: str) -> dict:
    return {
        "prediction": "Uncertain",
        "confidence": None,
        "fake_probability": None,
        "summary": reason,
        "model_version": UNAVAILABLE_MODEL_VERSION,
        "detected_language": language,
        "is_stub": True,
        "status": "unavailable",
        "input_truncated": False,
    }


def classifier_for_language(language: str):
    """Return a supported language's classifier without routing English to Roman Urdu."""
    script = xlmr.LANGUAGE_TO_MODEL.get(language)
    if script is None:
        return None, None, None
    try:
        classifier, reason = xlmr.get_classifier(script)
    except Exception:
        logger.exception("Could not initialize %s XLM-R classifier", script)
        return script, None, "The trained text model could not be initialized. Check backend logs."
    return script, classifier, reason


def long_article_model(text: str, language: str):
    """The long-article TF-IDF pipeline when it should handle this text, else None."""
    if language != "urdu" or not long_articles.is_long(text):
        return None
    pipeline, reason = long_articles.get_model()
    if pipeline is None:
        logger.info("Long Urdu text goes to the XLM-R model: %s", reason)
    return pipeline


def predict_text(text: str, language: Optional[str] = None) -> dict:
    """Run real inference for detected Urdu/Roman Urdu; report other input unavailable.

    `language` is accepted for existing callers, but detector output remains authoritative
    so OCR tags such as `en`/`ur` cannot route text to an incompatible checkpoint.
    """
    if not isinstance(text, str) or not text.strip():
        return _unavailable("unknown", "Enter some text before submitting it for analysis.")

    resolved_language = detect_language(text)
    script, classifier, reason = classifier_for_language(resolved_language)
    if script is None:
        if resolved_language == "english":
            return _unavailable(resolved_language, "English classification is not connected; only Urdu and Roman Urdu models are available.")
        if resolved_language == "mixed":
            return _unavailable(resolved_language, "Mixed Urdu-script and Latin-script text is not supported by either text model.")
        return _unavailable(resolved_language, "The input language could not be identified reliably, so no model was selected.")
    pipeline = long_article_model(text, resolved_language)
    if pipeline is not None:
        try:
            result = long_articles.predict(pipeline, text)
            return {
                **result,
                "detected_language": resolved_language,
                "summary": (
                    f"The long-article Urdu model (TF-IDF, trained on full FIRE 2021 articles) predicted "
                    f"{result['prediction'].lower()}. Its score is not independent verification of the claim."
                ),
            }
        except Exception:
            logger.exception("Long-article Urdu model inference failed; using the Urdu XLM-R model")
    if classifier is None:
        language_name = "Urdu" if script == "urdu" else "Roman Urdu"
        return _unavailable(resolved_language, reason or f"The trained {language_name} model is unavailable.")

    try:
        result = classifier.predict(text)
        if result.get("prediction") not in {"Real", "Fake"}:
            raise ValueError("XLM-R returned a label outside its verified label mapping")
        if result.get("confidence") is None or result.get("fake_probability") is None:
            raise ValueError("XLM-R returned no score")
        label_language = "Urdu-script" if script == "urdu" else "Roman Urdu"
        if result.get("input_truncated"):
            detail = (
                f" Input was truncated to the model's {result['max_input_tokens']}-token training limit."
            )
        else:
            detail = ""
        return {
            **result,
            "detected_language": resolved_language,
            "summary": (
                f"The trained {label_language} XLM-R model predicted {result['prediction'].lower()}. "
                "Its score is not independent verification of the claim." + detail
            ),
            "is_stub": False,
            "status": "completed",
        }
    except Exception:
        logger.exception("%s XLM-R inference failed", script)
        return _unavailable(resolved_language, f"The trained {script.replace('_', ' ')} model could not complete inference.")
