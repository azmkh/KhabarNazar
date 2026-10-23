"""Long-article TF-IDF model for Urdu script (text_module/urdu, trained on FIRE 2021).

The Urdu XLM-R checkpoint was trained on short news items and only reads its first 64
tokens, so Urdu text longer than LONG_TEXT_WORDS words goes to this word + character
TF-IDF + Logistic Regression pipeline instead, which scored better on full articles
(macro-F1 0.639 on the FIRE 2021 test set, as reported in text_module/urdu).

The artifact is a bare scikit-learn pipeline saved with joblib by the notebook
(text_module/urdu/notebooks/urdu_fake_news_xlmr.ipynb). Its classes are 0 = real and
1 = fake (label_from_name / the FIRE label sheet in that notebook). It must be loaded with
the scikit-learn version it was saved with (pinned in requirements.txt).
"""

from __future__ import annotations

import logging
import math
import os
import re
import threading
from functools import lru_cache
from pathlib import Path
from typing import Optional

from app.ai.text.preprocess import clean_urdu_notebook
from app.config import BASE_DIR, settings

logger = logging.getLogger(__name__)

DEFAULT_MODEL_PATH = BASE_DIR.parent / "text_module" / "urdu" / "models" / "tfidf_long_articles.joblib"
MODEL_VERSION = "tfidf-urdu-long-articles"
LABELS = {0: "Real", 1: "Fake"}  # training notebook: real = 0, fake = 1
_LOAD_LOCK = threading.Lock()
_TOKEN = re.compile(r"\w+", flags=re.UNICODE)

def is_long(text: str) -> bool:
    return len(text.split()) > settings.LONG_TEXT_WORDS


def model_path() -> Path:
    configured = os.environ.get("KHABARNAZAR_TEXT_MODEL_PATH") or settings.TEXT_MODEL_PATH
    return Path(configured).expanduser() if configured else DEFAULT_MODEL_PATH


@lru_cache(maxsize=2)
def _load(path: str, modified_at: int):
    del modified_at  # part of the cache key, so replacing the file reloads it
    import joblib

    pipeline = joblib.load(path)
    classes = [int(value) for value in getattr(pipeline, "classes_", [])]
    if sorted(classes) != sorted(LABELS):
        raise ValueError(f"long-article model has classes {classes}, expected 0 (real) and 1 (fake)")
    return pipeline


def get_model() -> tuple[Optional[object], Optional[str]]:
    """Return (pipeline, None) or (None, reason it is unavailable)."""
    path = model_path()
    if not path.is_file():
        return None, "The long-article Urdu model file is not installed."
    try:
        with _LOAD_LOCK:
            return _load(str(path.resolve()), path.stat().st_mtime_ns), None
    except ImportError:
        return None, "The long-article Urdu model needs scikit-learn and joblib."
    except Exception:
        logger.exception("Could not load the long-article Urdu model from %s", path)
        return None, "The long-article Urdu model could not be loaded. Check backend logs."


def _fake_probability(pipeline, cleaned: str) -> float:
    classes = [int(value) for value in pipeline.classes_]
    probability = float(pipeline.predict_proba([cleaned])[0][classes.index(1)])
    if not math.isfinite(probability) or not 0 <= probability <= 1:
        raise ValueError("long-article model returned an invalid Fake probability")
    return probability


def predict(pipeline, text: str) -> dict:
    fake_probability = _fake_probability(pipeline, clean_urdu_notebook(text))
    prediction = LABELS[1] if fake_probability >= 0.5 else LABELS[0]
    return {
        "prediction": prediction,
        "confidence": round(max(fake_probability, 1.0 - fake_probability), 4),
        "fake_probability": round(fake_probability, 4),
        "model_version": MODEL_VERSION,
        "is_stub": False,
        "status": "completed",
        "input_truncated": False,  # TF-IDF reads the whole article
    }


def explain(pipeline, text: str, top_k: int) -> list[dict]:
    """Exact attribution from the linear model: each feature's TF-IDF value times its weight,
    shared out over the words it overlaps (ported from text_module's backend explanation)."""
    cleaned = clean_urdu_notebook(text)
    features, classifier = pipeline.steps[0][1], pipeline.steps[-1][1]
    row = features.transform([cleaned]).tocsr()
    names = features.get_feature_names_out()
    predicted_fake = _fake_probability(pipeline, cleaned) >= 0.5
    # A binary LogisticRegression's coefficients point toward classes_[1] (fake).
    coefficients = classifier.coef_[0] * (1.0 if predicted_fake else -1.0)

    lowered = cleaned.casefold()
    tokens = [(match.group(0), match.start(), match.end()) for match in _TOKEN.finditer(lowered)]
    totals: dict[tuple[str, int, int], float] = {}
    for column, value in zip(row.indices, row.data):
        _, separator, feature = str(names[column]).partition("__")
        if not separator or not feature:
            continue
        contribution = float(value * coefficients[column])
        needle = feature.casefold()
        occurrences, start = [], 0
        while (found := lowered.find(needle, start)) >= 0:
            occurrences.append((found, found + len(needle)))
            start = found + 1
        for feature_start, feature_end in occurrences:
            overlapping = [token for token in tokens if token[1] < feature_end and token[2] > feature_start]
            for token in overlapping:
                totals[token] = totals.get(token, 0.0) + contribution / (len(occurrences) * len(overlapping))

    by_word: dict[str, float] = {}
    for (word, _, _), score in totals.items():
        by_word[word] = by_word.get(word, 0.0) + score
    ranked = sorted(by_word.items(), key=lambda item: abs(item[1]), reverse=True)[:max(0, top_k)]
    return [
        {"word": word, "contribution": round(score, 5),
         "direction": "supports_prediction" if score >= 0 else "opposes_prediction"}
        for word, score in ranked
    ]
