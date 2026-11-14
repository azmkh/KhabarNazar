"""Language-aware routing to the separately trained text models.

Every text with letters is classified; nothing is refused because of its language or its words.

| Input                                          | Model                                         |
|------------------------------------------------|-----------------------------------------------|
| Urdu script, up to LONG_TEXT_WORDS words       | Urdu XLM-R (Hook and Bait)                    |
| Urdu script, longer (full articles)            | TF-IDF + Logistic Regression (FIRE 2021)      |
| Mixed script, mostly Urdu letters              | the Urdu models, as above                     |
| Roman Urdu, English, other or unclear Latin    | Roman Urdu XLM-R (512-token limit)            |
| No letters at all (only digits or symbols)     | none: an explicit Uncertain result            |

English has no model of its own. It goes to the Roman Urdu XLM-R (a multilingual XLM-R large,
fine-tuned on Roman Urdu news only), and the result says so: it is less reliable than Roman Urdu.
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
ARABIC_SCRIPT = ("\u0600", "\u06ff")

# Shown with results when the text is not plain Urdu or Roman Urdu, so the reader knows which
# model actually read it.
ROUTING_NOTES = {
    "english": (
        " The text looks like English. There is no English classifier, so it was checked with the Roman Urdu "
        "classifier, which was not trained on English; treat this result as less reliable."
    ),
    "unknown": " The language was not clearly identified, so the text was checked with the Roman Urdu classifier.",
}


def model_language(text: str, detected: str) -> Optional[str]:
    """Which trained model reads this text: "urdu" or "roman_urdu". None only with no letters.

    Detection only labels the text; it never stops it from being classified.
    """
    letters = [character for character in text if character.isalpha()]
    if not letters:
        return None
    if detected in SUPPORTED_TEXT_LANGUAGES:
        return detected
    urdu_letters = sum(ARABIC_SCRIPT[0] <= character <= ARABIC_SCRIPT[1] for character in letters)
    return "urdu" if urdu_letters / len(letters) >= 0.5 else "roman_urdu"


def routing_note(detected: str, route: str) -> str:
    """A sentence saying which model read the text when it is not plain Urdu or Roman Urdu."""
    if detected == "mixed":
        name = "Urdu" if route == "urdu" else "Roman Urdu"
        return f" The text mixes Urdu and Latin script; it was checked with the {name} classifier, for its main script."
    return ROUTING_NOTES.get(detected, "")


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
    """Return the classifier for a model language ("urdu" or "roman_urdu"; see model_language)."""
    script = xlmr.LANGUAGE_TO_MODEL.get(language)
    if script is None:
        return None, None, None
    try:
        classifier, reason = xlmr.get_classifier(script)
    except Exception:
        logger.exception("Could not initialize %s XLM-R classifier", script)
        return script, None, "The text classifier could not be started. Check backend logs."
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
    """Classify any text that has letters with the trained model for its script.

    `language` is accepted for existing callers, but the text itself decides the model, so OCR
    tags such as `en`/`ur` cannot route text to the wrong checkpoint.
    """
    if not isinstance(text, str) or not text.strip():
        return _unavailable("unknown", "Enter some text before submitting it for analysis.")

    resolved_language = detect_language(text)
    route = model_language(text, resolved_language)
    if route is None:
        return _unavailable(resolved_language, "The text has no words to classify (only numbers or symbols).")
    note = routing_note(resolved_language, route)
    script, classifier, reason = classifier_for_language(route)
    pipeline = long_article_model(text, route)
    if pipeline is not None:
        try:
            result = long_articles.predict(pipeline, text)
            return {
                **result,
                "detected_language": resolved_language,
                "summary": (
                    f"The long-article Urdu classifier (TF-IDF, trained on full FIRE 2021 articles) predicted "
                    f"{result['prediction'].lower()}. Its score is not independent verification of the claim."
                    + note
                ),
                "model_language": route,
            }
        except Exception:
            logger.exception("Long-article Urdu model inference failed; using the Urdu XLM-R model")
    if classifier is None:
        language_name = "Urdu" if script == "urdu" else "Roman Urdu"
        return _unavailable(resolved_language, reason or f"The trained {language_name} classifier is unavailable.")

    try:
        result = classifier.predict(text)
        if result.get("prediction") not in {"Real", "Fake"}:
            raise ValueError("XLM-R returned a label outside its verified label mapping")
        if result.get("confidence") is None or result.get("fake_probability") is None:
            raise ValueError("XLM-R returned no score")
        label_language = "Urdu-script" if script == "urdu" else "Roman Urdu"
        if result.get("input_truncated"):
            detail = (
                f" Input was truncated to the classifier's {result['max_input_tokens']}-token training limit."
            )
        else:
            detail = ""
        return {
            **result,
            "detected_language": resolved_language,
            "summary": (
                f"The trained {label_language} XLM-R classifier predicted {result['prediction'].lower()}. "
                "Its score is not independent verification of the claim." + detail + note
            ),
            "model_language": route,
            "is_stub": False,
            "status": "completed",
        }
    except Exception:
        logger.exception("%s XLM-R inference failed", script)
        return _unavailable(resolved_language, f"The trained {script.replace('_', ' ')} classifier could not complete the check.")
