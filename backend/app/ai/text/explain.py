"""Bounded occlusion explanations for the Urdu and Roman Urdu XLM-R models."""

from __future__ import annotations

import logging

from app.ai.text.language_detection import detect_language
from app.ai.text.predict import classifier_for_language

logger = logging.getLogger(__name__)
MAX_EXPLANATION_WORDS = 8


def explain_text(
    text: str,
    top_k: int = 8,
    language: str | None = None,
    prediction: dict | None = None,
) -> dict:
    """Show words that influence the selected model's label, not fact verification."""
    detected = detect_language(text)
    script, classifier, reason = classifier_for_language(detected)
    if script is None or classifier is None:
        return {
            "highlighted_words": [],
            "summary": "No model-based word explanation is available for this input language.",
            "is_stub": True,
        }

    try:
        prediction = prediction or classifier.predict(text)
        language_name = "Urdu-script" if script == "urdu" else "Roman Urdu"
        if prediction.get("input_truncated"):
            return {
                "highlighted_words": [],
                "summary": (
                    f"The {language_name} model predicted {prediction['prediction']}. The input was "
                    f"truncated to {prediction['max_input_tokens']} model tokens. Word-level attribution "
                    "is omitted for truncated text; the model output is not fact verification."
                ),
                "is_stub": False,
            }
        highlights = classifier.explain(
            text,
            top_k=min(max(0, top_k), MAX_EXPLANATION_WORDS),
            max_words=MAX_EXPLANATION_WORDS,
            base_fake_probability=prediction.get("fake_probability"),
        )
        summary = (
            f"The {language_name} model predicted {prediction['prediction']}. Word highlights show how "
            "removing each selected word changed the model output; they are not fact verification."
        )
        return {"highlighted_words": highlights, "summary": summary, "is_stub": False}
    except Exception:
        logger.exception("%s XLM-R explanation failed", script)
        return {
            "highlighted_words": [],
            "summary": "The model result is available, but its word explanation could not be generated.",
            "is_stub": True,
        }
