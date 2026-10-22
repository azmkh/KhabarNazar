"""Word-level explanations for the text classifiers.

- TF-IDF model: exact feature attribution from the linear model's weights.
- XLM-R models: occlusion. Each word is removed in turn and the change in the
  model's probability for its predicted label is measured.

Either way, a highlight shows what influenced the model output; it is not
evidence that a claim is true or false. Offsets are intentionally omitted
because Unicode normalization can change character positions.
"""

from __future__ import annotations

import re
from typing import Any, Optional

from app.ai.text.predict import DEFAULT_LABEL_MAP, choose_model
from app.ai.text.preprocess import normalize_text


TOKEN_PATTERN = re.compile(r"\w+", flags=re.UNICODE)
# Occlusion runs one forward pass per distinct word; cap it to keep requests fast.
MAX_OCCLUSION_WORDS = 40


def _highlights(totals: dict, top_k: int) -> list[dict]:
    return [
        {
            "word": word,
            "contribution": round(score, 5),
            "direction": "supports_prediction" if score >= 0 else "opposes_prediction",
        }
        for word, score in sorted(totals.items(), key=lambda item: abs(item[1]), reverse=True)[:max(0, top_k)]
    ]


def _explain_tfidf(bundle: dict, text: str, top_k: int) -> tuple[list[dict], str]:
    pipeline = bundle["model"]
    normalized = normalize_text(text)
    # Works for the backend training script's Pipeline(features, classifier)
    # and for a plain make_pipeline(make_union(...), LogisticRegression()).
    feature_union = pipeline.named_steps.get("features", pipeline.steps[0][1])
    classifier = pipeline.named_steps.get("classifier", pipeline.steps[-1][1])
    sparse_features = feature_union.transform([normalized]).tocsr()
    names = feature_union.get_feature_names_out()
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
            overlapping = [token for token in tokens if token[1] < feature_end and token[2] > feature_start]
            if not overlapping:
                continue
            share = contribution / (len(occurrences) * len(overlapping))
            for token in overlapping:
                totals[token] = totals.get(token, 0.0) + share

    # totals is keyed by (word, start, end); keep only the word in the output.
    highlights = [{**item, "word": item["word"][0]} for item in _highlights(totals, top_k)]
    label_map = {str(k): v for k, v in bundle.get("label_map", DEFAULT_LABEL_MAP).items()}
    return highlights, str(label_map[str(predicted_class)])


def _explain_xlmr(classifier, text: str, top_k: int) -> tuple[list[dict], str]:
    normalized = normalize_text(text)
    base_fake = classifier.fake_probabilities([normalized])[0]
    label = "Fake" if base_fake >= 0.5 else "Real"
    sign = 1.0 if label == "Fake" else -1.0

    words: list[str] = []
    for match in TOKEN_PATTERN.finditer(normalized):
        word = match.group(0)
        if word not in words:
            words.append(word)
        if len(words) >= MAX_OCCLUSION_WORDS:
            break
    if not words:
        return [], label

    variants = [
        " ".join(re.sub(rf"(?<!\w){re.escape(word)}(?!\w)", " ", normalized).split()) or "."
        for word in words
    ]
    occluded_fake = classifier.fake_probabilities(variants)
    # Positive = removing the word lowers the probability of the predicted label,
    # i.e. the word supported the prediction.
    totals = {word: sign * (base_fake - fake) for word, fake in zip(words, occluded_fake)}
    return _highlights(totals, top_k), label


def explain_text(text: str, top_k: int = 12, language: Optional[str] = None) -> dict[str, Any]:
    """Return word contributions from the same model predict_text() uses."""
    kind, model, _ = choose_model(text, language)
    if kind == "unavailable":
        return {
            "highlighted_words": [],
            "summary": f"No word highlights are available. {model}",
            "is_stub": True,
        }

    if kind == "xlmr":
        highlights, label = _explain_xlmr(model, text, top_k)
        method = "Highlights show how much removing each word changes the model's output"
    else:
        highlights, label = _explain_tfidf(model, text, top_k)
        method = "Highlights show tokens that most influenced this model output"

    if highlights:
        summary = f"The model predicted {label}. {method}; they are not fact verification."
    else:
        summary = f"The model predicted {label}, but it found no token-level features to display."
    return {"highlighted_words": highlights, "summary": summary, "is_stub": False}
