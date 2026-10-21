"""XLM-RoBERTa Urdu fake news model (trained in text_module/notebooks).

The model folder (about 1 GB) is not in git. Train it with the notebook, which saves it to
models/text/xlmr/, or point KHABARNAZAR_TEXT_TRANSFORMER_DIR at another folder.
PyTorch and transformers are imported lazily, so the API still starts without them and
predict.py falls back to the TF-IDF model or an "unavailable" result.
"""

from __future__ import annotations

import json
import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

from app.ai.text.preprocess import clean_urdu_for_model

logger = logging.getLogger(__name__)

DEFAULT_TRANSFORMER_DIR = Path(__file__).resolve().parents[4] / "models" / "text" / "xlmr"
# Languages the model was trained on (Hook and Bait is Urdu script only).
SUPPORTED_LANGUAGES = {"urdu", "mixed"}
FAKE_INDEX = 1  # training convention: 0 = REAL, 1 = FAKE


def transformer_dir() -> Path:
    return Path(os.environ.get("KHABARNAZAR_TEXT_TRANSFORMER_DIR", str(DEFAULT_TRANSFORMER_DIR))).expanduser()


class UrduTransformer:
    def __init__(self, model_dir: Path):
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        config_path = model_dir / "khabarnazar_config.json"
        config = json.loads(config_path.read_text(encoding="utf-8")) if config_path.is_file() else {}
        self.torch = torch
        self.max_len = int(config.get("max_len", 128))
        self.model_version = str(config.get("model_version", "text-xlmr-hookbait"))[:50]
        self.remove_punctuation = bool(config.get("remove_punctuation", False))
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.tokenizer = AutoTokenizer.from_pretrained(str(model_dir))
        self.model = AutoModelForSequenceClassification.from_pretrained(str(model_dir)).to(self.device).eval()

    def clean(self, text: object) -> str:
        """Clean exactly as the training notebook did for this model."""
        return clean_urdu_for_model(text, remove_punctuation=self.remove_punctuation)

    def fake_probabilities(self, texts: list[str], batch_size: int = 32) -> list[float]:
        """Probability of Fake for already-cleaned texts."""
        results: list[float] = []
        with self.torch.no_grad():
            for start in range(0, len(texts), batch_size):
                encoded = self.tokenizer(texts[start:start + batch_size], truncation=True,
                                         max_length=self.max_len, padding=True, return_tensors="pt").to(self.device)
                probabilities = self.torch.softmax(self.model(**encoded).logits, dim=-1)[:, FAKE_INDEX]
                results.extend(float(value) for value in probabilities.cpu())
        return results


@lru_cache(maxsize=2)
def _load(path: str, modified_at: int) -> UrduTransformer:
    del modified_at  # part of the cache key, so replacing the model reloads it
    return UrduTransformer(Path(path))


def load_transformer() -> tuple[Optional[UrduTransformer], Optional[str]]:
    """Return (model, None) or (None, reason it is unavailable)."""
    model_dir = transformer_dir()
    weights = [model_dir / "model.safetensors", model_dir / "pytorch_model.bin"]
    present = next((path for path in weights if path.is_file()), None)
    if present is None:
        return None, "Urdu transformer model not found. Train it with text_module/notebooks first."
    try:
        return _load(str(model_dir.resolve()), present.stat().st_mtime_ns), None
    except ImportError:
        return None, "Urdu transformer model found, but torch/transformers are not installed in the backend environment."
    except Exception:
        logger.exception("Could not load Urdu transformer model from %s", model_dir)
        return None, "Urdu transformer model could not be loaded. Check the backend log."


def predict_with_transformer(model: UrduTransformer, text: str) -> dict:
    p_fake = model.fake_probabilities([model.clean(text)])[0]
    prediction = "Fake" if p_fake >= 0.5 else "Real"
    return {
        "prediction": prediction,
        "confidence": round(max(p_fake, 1 - p_fake), 4),
        "fake_probability": round(p_fake, 4),
        "model_version": model.model_version,
    }


def explain_with_transformer(model: UrduTransformer, text: str, top_k: int = 12, max_words: int = 80) -> list[dict]:
    """Word importance by occlusion: how much the predicted label's probability drops when a word is removed.

    This explains the actual transformer (unlike borrowing the TF-IDF model's weights).
    Cost is one extra forward pass per word, so only the first max_words words are scored;
    words past the model's input limit are truncated away anyway.
    """
    words = model.clean(text).split()[:max_words]
    if not words:
        return []
    variants = [" ".join(words)] + [" ".join(words[:i] + words[i + 1:]) for i in range(len(words))]
    probabilities = model.fake_probabilities(variants)
    full = probabilities[0]
    predicted_fake = full >= 0.5

    def label_probability(p: float) -> float:
        return p if predicted_fake else 1 - p

    totals: dict[str, float] = {}
    for word, p_without in zip(words, probabilities[1:]):
        contribution = label_probability(full) - label_probability(p_without)
        totals[word] = totals.get(word, 0.0) + contribution
    ranked = sorted(totals.items(), key=lambda item: abs(item[1]), reverse=True)[:max(0, top_k)]
    return [
        {
            "word": word,
            "contribution": round(score, 5),
            "direction": "supports_prediction" if score >= 0 else "opposes_prediction",
        }
        for word, score in ranked
    ]
