"""XLM-RoBERTa text classifiers (Urdu script and Roman Urdu), loaded lazily.

Model folders are Hugging Face `save_pretrained` directories (config.json,
model weights, tokenizer files). They are ~1 GB each and are not stored in git:
download them into text_module/<urdu|roman_urdu>/models/xlmr/ (see
text_module/README.md) or point the
environment variables below at another folder.

torch and transformers are imported only when a model folder exists, so the
API (and its tests) still run on machines without them.
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

TEXT_MODULE = Path(__file__).resolve().parents[4] / "text_module"
DIR_ENV = {"urdu": "KHABARNAZAR_URDU_XLMR_DIR", "roman": "KHABARNAZAR_ROMAN_XLMR_DIR"}
DEFAULT_DIRS = {
    "urdu": TEXT_MODULE / "urdu" / "models" / "xlmr",
    "roman": TEXT_MODULE / "roman_urdu" / "models" / "xlmr",
}
# Fallback when a model's config does not name its labels (e.g. LABEL_0 / LABEL_1).
FAKE_INDEX_ENV = {"urdu": "KHABARNAZAR_URDU_FAKE_INDEX", "roman": "KHABARNAZAR_ROMAN_FAKE_INDEX"}
MODEL_VERSION = {"urdu": "xlmr-urdu", "roman": "xlmr-roman-urdu"}


def max_length() -> int:
    return int(os.environ.get("KHABARNAZAR_XLMR_MAX_LEN", "512"))  # Roman Urdu model was trained on 512 tokens


def model_dir(script: str) -> Path:
    return Path(os.environ.get(DIR_ENV[script], str(DEFAULT_DIRS[script]))).expanduser()


def is_configured(script: str) -> bool:
    """True if a model folder for this script exists (it may still fail to load)."""
    return (model_dir(script) / "config.json").is_file()


def _resolve_fake_index(id2label: dict, script: str) -> int:
    for index, name in id2label.items():
        if "fake" in str(name).lower():
            return int(index)
    fallback = int(os.environ.get(FAKE_INDEX_ENV[script], "1"))
    logger.warning(
        "%s model labels %s do not name 'fake'; using index %s as Fake (set %s to change).",
        script, id2label, fallback, FAKE_INDEX_ENV[script],
    )
    return fallback


class XlmrClassifier:
    def __init__(self, path: Path, script: str):
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        self._torch = torch
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.tokenizer = AutoTokenizer.from_pretrained(path)
        self.model = AutoModelForSequenceClassification.from_pretrained(path).eval().to(self.device)
        self.fake_index = _resolve_fake_index(self.model.config.id2label, script)
        self.model_version = MODEL_VERSION[script]

    def fake_probabilities(self, texts: list[str], batch_size: int = 16) -> list[float]:
        """Probability of Fake for each text."""
        results: list[float] = []
        with self._torch.no_grad():
            for start in range(0, len(texts), batch_size):
                batch = texts[start:start + batch_size]
                encoded = self.tokenizer(
                    batch, truncation=True, max_length=max_length(), padding=True, return_tensors="pt"
                ).to(self.device)
                probabilities = self._torch.softmax(self.model(**encoded).logits, dim=-1)
                results.extend(float(value) for value in probabilities[:, self.fake_index].cpu())
        return results


@lru_cache(maxsize=4)
def _load(path: str, modified_at: int, script: str) -> XlmrClassifier:
    # mtime in the cache key: replacing a model folder activates the new model.
    del modified_at
    return XlmrClassifier(Path(path), script)


def get_classifier(script: str) -> tuple[Optional[XlmrClassifier], Optional[str]]:
    """Return (classifier, None) or (None, reason it is unavailable)."""
    path = model_dir(script)
    config = path / "config.json"
    if not config.is_file():
        return None, f"No {script} XLM-R model folder at {path}."
    try:
        return _load(str(path.resolve()), config.stat().st_mtime_ns, script), None
    except ImportError:
        return None, "XLM-R model found, but torch/transformers are not installed in the backend environment."
    except Exception:
        logger.exception("Could not load %s XLM-R model from %s", script, path)
        return None, f"The {script} XLM-R model could not be loaded. Check the backend log."
