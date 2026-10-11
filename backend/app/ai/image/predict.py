"""Image manipulation/authenticity model interface.

This is deliberately separate from OCR (see ocr.py): whether the pixels were
edited says nothing about whether the news claim in the image is true.
"""

from __future__ import annotations


def analyze_image(image_path: str) -> dict:
    """Return unavailable until a validated image manipulation model is supplied.

    OCR text analysis is a separate signal and is deliberately not used to infer
    whether the image pixels are authentic or the news claim is true.
    """
    # Keep manipulation_prediction short: it is stored in a VARCHAR(50) column.
    return {
        "image_score": None,
        "manipulation_prediction": "Not Analyzed",
        "is_stub": True,
        "status": "model_unavailable",
        "summary": "Image manipulation was not analyzed because no trained manipulation model is configured.",
    }
