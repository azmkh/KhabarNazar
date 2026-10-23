"""Cached XLM-R inference for Urdu script and Roman Urdu.

The two languages use separate trained checkpoints and preprocessing. Training stays
in text_module; this module only loads saved artifacts and performs inference.
"""

from __future__ import annotations

import json
import logging
import math
import os
import re
import threading
from functools import lru_cache
from pathlib import Path
from typing import Optional

from app.ai.text.preprocess import USING_URDUHACK, clean_urdu_for_model
from app.config import BASE_DIR, settings

logger = logging.getLogger(__name__)

TEXT_MODULE = BASE_DIR.parent / "text_module"
LEGACY_URDU_DIR = BASE_DIR.parent / "models" / "text" / "xlmr"
DEFAULT_DIRS = {
    "urdu": TEXT_MODULE / "urdu" / "models" / "xlmr",
    "roman": TEXT_MODULE / "roman_urdu" / "models" / "xlmr",
}
TRAINING_MAX_LEN = {"urdu": 64, "roman": 512}
MODEL_VERSION = {"urdu": "xlmr-urdu", "roman": "xlmr-roman-urdu"}
LANGUAGE_TO_MODEL = {"urdu": "urdu", "roman_urdu": "roman"}
_LOAD_LOCK = threading.Lock()
_WORD = re.compile(r"\w+", flags=re.UNICODE)


def model_dir(script: str) -> Path:
    if script not in DEFAULT_DIRS:
        raise ValueError("Unknown XLM-R model script")
    env_name = "KHABARNAZAR_URDU_XLMR_DIR" if script == "urdu" else "KHABARNAZAR_ROMAN_XLMR_DIR"
    configured = os.environ.get(env_name) or (
        settings.URDU_XLMR_DIR if script == "urdu" else settings.ROMAN_XLMR_DIR
    )
    if configured:
        return Path(configured).expanduser()
    if script == "urdu" and _artifact_files_present(LEGACY_URDU_DIR):
        # Reuse the already-present Urdu model instead of downloading a duplicate.
        return LEGACY_URDU_DIR
    return DEFAULT_DIRS[script]


def configured_max_length(script: str, metadata_max_len: int | None = None) -> int:
    """Resolve a per-model override, preserving the legacy max setting for Roman Urdu."""
    if script == "urdu":
        raw = os.environ.get("KHABARNAZAR_URDU_XLMR_MAX_LEN")
        requested = int(raw) if raw is not None else settings.URDU_XLMR_MAX_LEN
        trained_limit = metadata_max_len if metadata_max_len is not None else TRAINING_MAX_LEN[script]
    elif script == "roman":
        raw = os.environ.get("KHABARNAZAR_ROMAN_XLMR_MAX_LEN")
        shared = os.environ.get("KHABARNAZAR_XLMR_MAX_LEN")
        requested = int(raw) if raw is not None else (
            settings.ROMAN_XLMR_MAX_LEN or (int(shared) if shared is not None else settings.XLMR_MAX_LEN)
        )
        trained_limit = TRAINING_MAX_LEN[script]
    else:
        raise ValueError("Unknown XLM-R model script")

    effective = requested if requested is not None else trained_limit
    if effective < 3 or effective > trained_limit:
        raise ValueError(f"{script} XLM-R max length must be between 3 and its trained limit ({trained_limit})")
    return effective


def _artifact_files_present(path: Path) -> bool:
    has_weights = any((path / name).is_file() and (path / name).stat().st_size > 0
                      for name in ("model.safetensors", "pytorch_model.bin"))
    has_tokenizer = (path / "tokenizer.json").is_file() or (path / "sentencepiece.bpe.model").is_file()
    return (path / "config.json").is_file() and has_weights and has_tokenizer


def is_configured(script: str) -> bool:
    return _artifact_files_present(model_dir(script))


def _labels_from_config(config, script: str) -> tuple[dict[int, str], int]:
    raw = getattr(config, "id2label", {}) or {}
    labels = {int(index): str(label).strip().casefold() for index, label in raw.items()}
    if set(labels.values()) != {"real", "fake"}:
        raise ValueError(f"{script} XLM-R checkpoint must define exactly REAL and FAKE labels")
    fake_index = next(index for index, label in labels.items() if label == "fake")
    return labels, fake_index


class XlmrClassifier:
    def __init__(self, path: Path, script: str):
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        if script not in LANGUAGE_TO_MODEL.values():
            raise ValueError("Unknown XLM-R model script")
        if not _artifact_files_present(path):
            raise ValueError(f"{script} XLM-R checkpoint is incomplete")

        metadata = {}
        metadata_path = path / "khabarnazar_config.json"
        if metadata_path.is_file():
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        metadata_max = int(metadata["max_len"]) if script == "urdu" and metadata.get("max_len") else None
        max_len = configured_max_length(script, metadata_max)

        self.torch = torch
        self.script = script
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.tokenizer = AutoTokenizer.from_pretrained(str(path), local_files_only=True)
        self.model = AutoModelForSequenceClassification.from_pretrained(
            str(path), local_files_only=True
        ).to(self.device).eval()
        if getattr(self.model.config, "model_type", None) != "xlm-roberta":
            raise ValueError(f"{script} checkpoint is not an XLM-RoBERTa model")
        self.labels, self.fake_index = _labels_from_config(self.model.config, script)

        position_limit = int(self.model.config.max_position_embeddings)
        position_limit -= int(self.tokenizer.pad_token_id or 0) + 1
        tokenizer_limit = int(self.tokenizer.model_max_length)
        if tokenizer_limit >= 1_000_000:
            tokenizer_limit = position_limit
        safe_limit = min(position_limit, tokenizer_limit)
        if max_len > safe_limit:
            raise ValueError(
                f"{script} configured max length {max_len} exceeds tokenizer/model limit {safe_limit}"
            )
        self.max_len = max_len
        self.model_version = str(metadata.get("model_version", MODEL_VERSION[script]))[:50]
        self.remove_punctuation = bool(metadata.get("remove_punctuation", True)) if script == "urdu" else False
        if script == "urdu" and not USING_URDUHACK:
            raise ValueError("Urdu normalization dependency urduhack is unavailable")

    def prepare(self, text: str) -> str:
        if self.script == "urdu":
            return clean_urdu_for_model(text, remove_punctuation=self.remove_punctuation)
        # The Roman Urdu training notebook feeds roman_text directly to XLM-R.
        return text

    def token_count(self, text: str) -> int:
        encoded = self.tokenizer(
            self.prepare(text), add_special_tokens=True, truncation=False, verbose=False
        )
        return len(encoded["input_ids"])

    def fake_probabilities(self, texts: list[str], batch_size: int = 1) -> list[float]:
        results: list[float] = []
        with self.torch.inference_mode():
            for start in range(0, len(texts), batch_size):
                batch = [self.prepare(text) for text in texts[start:start + batch_size]]
                encoded = self.tokenizer(
                    batch, truncation=True, max_length=self.max_len, padding=True, return_tensors="pt"
                ).to(self.device)
                logits = self.model(**encoded).logits
                if logits.ndim != 2 or logits.shape[1] != len(self.labels) or not self.torch.isfinite(logits).all():
                    raise ValueError("XLM-R returned invalid logits")
                probabilities = self.torch.softmax(logits, dim=-1)
                if not self.torch.isfinite(probabilities).all():
                    raise ValueError("XLM-R returned non-finite probabilities")
                results.extend(float(value) for value in probabilities[:, self.fake_index].cpu())
        if any(not math.isfinite(value) or value < 0 or value > 1 for value in results):
            raise ValueError("XLM-R returned an invalid Fake probability")
        return results

    def predict(self, text: str) -> dict:
        tokens = self.token_count(text)
        fake_probability = self.fake_probabilities([text])[0]
        predicted_index = self.fake_index if fake_probability >= 0.5 else next(
            index for index, label in self.labels.items() if label == "real"
        )
        prediction = self.labels[predicted_index].title()
        return {
            "prediction": prediction,
            "confidence": round(max(fake_probability, 1.0 - fake_probability), 4),
            "fake_probability": round(fake_probability, 4),
            "model_version": self.model_version,
            "is_stub": False,
            "status": "completed",
            "input_truncated": tokens > self.max_len,
            "input_token_count": tokens,
            "max_input_tokens": self.max_len,
        }

    def explain(
        self,
        text: str,
        top_k: int = 8,
        max_words: int = 8,
        base_fake_probability: float | None = None,
    ) -> list[dict]:
        prepared = self.prepare(text)
        words = list(dict.fromkeys(match.group(0) for match in _WORD.finditer(prepared)))[:max_words]
        if not words:
            return []
        p_fake = (
            self.fake_probabilities([prepared])[0]
            if base_fake_probability is None else base_fake_probability
        )
        fake_label = p_fake >= 0.5
        full_label_score = p_fake if fake_label else 1.0 - p_fake
        variants = [re.sub(rf"(?<!\w){re.escape(word)}(?!\w)", " ", prepared) or "." for word in words]
        probabilities = self.fake_probabilities(variants)
        totals: dict[str, float] = {}
        for word, without_fake in zip(words, probabilities):
            without_score = without_fake if fake_label else 1.0 - without_fake
            totals[word] = full_label_score - without_score
        ranked = sorted(totals.items(), key=lambda item: abs(item[1]), reverse=True)[:max(0, top_k)]
        return [
            {"word": word, "contribution": round(score, 5),
             "direction": "supports_prediction" if score >= 0 else "opposes_prediction"}
            for word, score in ranked
        ]


@lru_cache(maxsize=2)
def _load(path: str, modified_at: int, script: str) -> XlmrClassifier:
    del modified_at
    return XlmrClassifier(Path(path), script)


def get_classifier(script: str) -> tuple[Optional[XlmrClassifier], Optional[str]]:
    path = model_dir(script)
    if not _artifact_files_present(path):
        return None, f"The trained {script.replace('_', ' ')} XLM-R model is unavailable or incomplete."
    weight = next(path / filename for filename in ("model.safetensors", "pytorch_model.bin")
                  if (path / filename).is_file())
    try:
        with _LOAD_LOCK:
            return _load(str(path.resolve()), weight.stat().st_mtime_ns, script), None
    except ImportError:
        return None, "XLM-R model found, but torch/transformers are not installed in the backend environment."
    except Exception:
        logger.exception("Could not load %s XLM-R model from %s", script, path)
        return None, f"The trained {script.replace('_', ' ')} XLM-R model could not be loaded. Check backend logs."


def warmup_models() -> None:
    for script in ("urdu", "roman"):
        if is_configured(script):
            get_classifier(script)
