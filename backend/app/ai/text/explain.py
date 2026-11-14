"""Word explanations from the same model predict_text() used.

- XLM-R models: bounded occlusion (each word removed in turn).
- Long-article TF-IDF model: exact attribution from the linear model's weights.
Either way a highlight shows what influenced the model output, not whether a claim is true.
"""

from __future__ import annotations

import logging

from app.ai.text.language_detection import detect_language
from app.ai.text import long_articles
from app.ai.text.predict import (
    LONG_ARTICLE_NOTE,
    REMINDER,
    classifier_for_language,
    long_article_model,
    model_language,
    predict_text,
    routing_note,
    verdict_summary,
)

logger = logging.getLogger(__name__)
MAX_EXPLANATION_WORDS = 8


def explain_text(
    text: str,
    top_k: int = 8,
    language: str | None = None,
    prediction: dict | None = None,
) -> dict:
    """Show words that influence the selected model's label, not fact verification."""
    # Explain the same model predict_text() used for this text.
    detected = detect_language(text)
    route = (prediction or {}).get("model_language") or model_language(text, detected)
    # Say which model read the text when it is not plain Urdu or Roman Urdu (English, mixed, unclear).
    note = routing_note(detected, route) if route else ""
    if prediction is None:
        # Explain the same model predict_text() would choose for this text.
        prediction = predict_text(text)
        if prediction.get("is_stub"):
            return {
                "highlighted_words": [],
                "summary": f"No word highlights are available. {prediction['summary']}",
                "is_stub": True,
            }
    if prediction.get("model_version") == long_articles.MODEL_VERSION:
        pipeline = long_article_model(text, route)
        if pipeline is not None:
            try:
                highlights = long_articles.explain(pipeline, text, top_k=min(max(0, top_k), MAX_EXPLANATION_WORDS))
                return {
                    "highlighted_words": highlights,
                    "summary": verdict_summary(prediction, words=bool(highlights)) + LONG_ARTICLE_NOTE + note + REMINDER,
                    "is_stub": False,
                }
            except Exception:
                logger.exception("Long-article Urdu explanation failed")
                return {
                    "highlighted_words": [],
                    "summary": "The result is available, but its word explanation could not be generated.",
                    "is_stub": True,
                }
    script, classifier, reason = classifier_for_language(route) if route else (None, None, None)
    if script is None or classifier is None:
        return {
            "highlighted_words": [],
            "summary": "No word explanation is available for this input language.",
            "is_stub": True,
        }

    try:
        if prediction.get("input_truncated"):
            # Word highlights are left out for long text: only its first part was read.
            return {
                "highlighted_words": [],
                "summary": verdict_summary(prediction, truncated=True) + note + REMINDER,
                "is_stub": False,
            }
        highlights = classifier.explain(
            text,
            top_k=min(max(0, top_k), MAX_EXPLANATION_WORDS),
            max_words=MAX_EXPLANATION_WORDS,
            base_fake_probability=prediction.get("fake_probability"),
        )
        summary = verdict_summary(prediction, words=bool(highlights)) + note + REMINDER
        return {"highlighted_words": highlights, "summary": summary, "is_stub": False}
    except Exception:
        logger.exception("%s XLM-R explanation failed", script)
        return {
            "highlighted_words": [],
            "summary": "The result is available, but its word explanation could not be generated.",
            "is_stub": True,
        }
