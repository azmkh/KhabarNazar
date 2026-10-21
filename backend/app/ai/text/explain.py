"""Feature attribution for the text models.

Urdu-script text handled by the XLM-RoBERTa model is explained by word occlusion
(transformer_model.explain_with_transformer); everything else uses the TF-IDF model's weights.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from app.ai.text.predict import load_text_model, uses_transformer
from app.ai.text.preprocess import normalize_text
from app.ai.text.transformer_model import explain_with_transformer

logger = logging.getLogger(__name__)


TOKEN_PATTERN = re.compile(r"\w+", flags=re.UNICODE)


def explain_text(text: str, top_k: int = 12) -> dict[str, Any]:
    """Return token contributions from the trained linear model, if available.

    Each contribution is a model feature attribution, not evidence that a claim
    is true or false. Offsets are intentionally omitted because Unicode
    normalization can change character positions.
    """
    transformer = uses_transformer(text)
    if transformer is not None:
        try:
            highlights = explain_with_transformer(transformer, text, top_k=top_k)
            p_fake = transformer.fake_probabilities([transformer.clean(text)])[0]
            label = "Fake" if p_fake >= 0.5 else "Real"
            summary = (
                f"The model predicted {label}. Highlights show how much removing each word changes the "
                "model's output; they are not fact verification."
                if highlights else f"The model predicted {label}, but it found no words to display."
            )
            return {"highlighted_words": highlights, "summary": summary, "is_stub": False}
        except Exception:
            logger.exception("Urdu transformer explanation failed; falling back to the TF-IDF model")

    bundle, reason = load_text_model()
    if bundle is None:
        return {
            "highlighted_words": [],
            "summary": f"No word highlights are available. {reason}",
            "is_stub": True,
        }

    pipeline = bundle["model"]
    normalized = normalize_text(text)
    feature_union = pipeline.named_steps["features"]
    sparse_features = feature_union.transform([normalized]).tocsr()
    names = feature_union.get_feature_names_out()
    classifier = pipeline.named_steps["classifier"]
    # Probabilities must come from the whole pipeline: the classifier step alone
    # expects TF-IDF features, not raw text.
    probabilities = pipeline.predict_proba([normalized])[0]
    predicted_index = int(probabilities.argmax())
    predicted_class = classifier.classes_[predicted_index]

    # LogisticRegression's binary coefficient row points toward classes_[1].
    coefficient_direction = 1.0 if predicted_index == 1 else -1.0
    coefficients = classifier.coef_[0] * coefficient_direction
    lowered = normalized.casefold()
    tokens = [(match.group(0), match.start(), match.end()) for match in TOKEN_PATTERN.finditer(lowered)]
    totals: dict[tuple[str, int, int], float] = {}

    for column, value in zip(sparse_features.indices, sparse_features.data):
        feature_name = str(names[column])
        _, separator, feature = feature_name.partition("__")
        if not separator or not feature:
            continue
        contribution = float(value * coefficients[column])
        needle = feature.casefold()
        start = 0
        occurrences = []
        while (found_at := lowered.find(needle, start)) >= 0:
            occurrences.append((found_at, found_at + len(needle)))
            start = found_at + 1
        for feature_start, feature_end in occurrences:
            overlapping = [
                token for token in tokens
                if token[1] < feature_end and token[2] > feature_start
            ]
            if not overlapping:
                continue
            share = contribution / (len(occurrences) * len(overlapping))
            for token in overlapping:
                totals[token] = totals.get(token, 0.0) + share

    highlights = [
        {
            "word": word,
            "contribution": round(score, 5),
            "direction": "supports_prediction" if score >= 0 else "opposes_prediction",
        }
        for (word, _, _), score in sorted(totals.items(), key=lambda item: abs(item[1]), reverse=True)[:max(0, top_k)]
    ]
    label = str({str(k): v for k, v in bundle["label_map"].items()}[str(predicted_class)])
    if highlights:
        summary = f"The model predicted {label}. Highlights show tokens that most influenced this model output; they are not fact verification."
    else:
        summary = f"The model predicted {label}, but it found no token-level features to display."
    return {"highlighted_words": highlights, "summary": summary, "is_stub": False}
