"""Conservative text cleanup shared by dataset preparation and later inference."""

import unicodedata


def normalize_text(value: object) -> str:
    """Normalize Unicode and whitespace without removing Urdu-specific marks."""
    if value is None:
        return ""
    text = unicodedata.normalize("NFKC", str(value))
    return " ".join(text.split())
