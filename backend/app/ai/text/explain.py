"""Word explanations from the same model predict_text() used.

- XLM-R models: bounded occlusion (each word removed in turn).
- Long-article TF-IDF model: exact attribution from the linear model's weights.
Either way a highlight shows what influenced the model output, not whether a claim is true.
"""

from __future__ import annotations

import logging

from app.ai.text.language_detection import detect_language
from app.ai.text import long_articles
from app.ai.text.predict import classifier_for_language, long_article_model, model_language, predict_text, routing_note

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
                    "summary": (
                        f"The long-article Urdu classifier predicted {prediction['prediction']}. Highlights show the "
                        "words whose features weighed most in this classifier's output; they are not fact verification."
                        + note
                    ),
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
        language_name = "Urdu-script" if script == "urdu" else "Roman Urdu"
        if prediction.get("input_truncated"):
            return {
                "highlighted_words": [],
                "summary": (
                    f"The {language_name} classifier predicted {prediction['prediction']}. The input was "
                    f"truncated to {prediction['max_input_tokens']} tokens. Word-level attribution "
                    "is omitted for truncated text; the classifier output is not fact verification."
                    + note
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
            f"The {language_name} classifier predicted {prediction['prediction']}. Word highlights show how "
            "removing each selected word changed the classifier output; they are not fact verification."
            + note
        )
        return {"highlighted_words": highlights, "summary": summary, "is_stub": False}
    except Exception:
        logger.exception("%s XLM-R explanation failed", script)
        return {
            "highlighted_words": [],
            "summary": "The result is available, but its word explanation could not be generated.",
            "is_stub": True,
        }
