"""Conservative text cleanup shared by dataset preparation and later inference."""

import importlib.util
import re
import sys
import types
import unicodedata


def normalize_text(value: object) -> str:
    """Normalize Unicode and whitespace without removing Urdu-specific marks."""
    if value is None:
        return ""
    text = unicodedata.normalize("NFKC", str(value))
    return " ".join(text.split())


# ---------------------------------------------------------------------------
# Cleaning for the XLM-RoBERTa Urdu model (text_module/notebooks).
# Training source is absent from this checkout, so exact parity cannot currently be
# verified. This is the checkpoint's documented normalization path; do not silently
# substitute fallback normalization for inference.
# ---------------------------------------------------------------------------

def _load_urduhack_normalize():
    """Import only urduhack.normalization (a plain `import urduhack` needs TensorFlow)."""
    spec = importlib.util.find_spec("urduhack")
    if spec is None:
        raise ImportError("urduhack not installed")
    if "urduhack" not in sys.modules:
        package = types.ModuleType("urduhack")
        package.__path__ = list(spec.submodule_search_locations)
        sys.modules["urduhack"] = package
    from urduhack.normalization import normalize
    return normalize


try:
    _urduhack_normalize = _load_urduhack_normalize()
    USING_URDUHACK = True
except Exception:  # Missing or broken urduhack: use the built-in character fixes below.
    _urduhack_normalize = None
    USING_URDUHACK = False

_ARABIC_TO_URDU = {"ي": "ی", "ى": "ی", "ك": "ک",
                   "ه": "ہ", "ة": "ۃ"}
_DIACRITICS = re.compile("[ً-ْٰ]")
_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
_URL = re.compile(r"https?://\S+|www\.\S+")
_HTML = re.compile(r"<[^>]+>")
_SPACES = re.compile(r"\s+")
_PUNCTUATION = re.compile(r"[۔،؟؛٪!?.,:;'\"‘’“”«»()\[\]{}\-–—…/\\|*_~`@#]+")


def _fallback_normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    for arabic, urdu in _ARABIC_TO_URDU.items():
        text = text.replace(arabic, urdu)
    return text


def clean_urdu_for_model(value: object, remove_punctuation: bool = False) -> str:
    """Urduhack normalization + link/HTML/diacritic/digit cleanup, as used in training.

    remove_punctuation must match the setting the model was trained with (stored as
    "remove_punctuation" in the model's khabarnazar_config.json).
    """
    if value is None:
        return ""
    text = _HTML.sub(" ", str(value))
    text = _URL.sub(" ", text)
    text = _urduhack_normalize(text) if _urduhack_normalize else _fallback_normalize(text)
    text = _DIACRITICS.sub("", text)
    text = text.translate(_DIGITS)
    text = text.replace("‌", " ").replace("​", "").replace("﻿", "")
    if remove_punctuation:
        text = _PUNCTUATION.sub(" ", text)
    return _SPACES.sub(" ", text).strip()
