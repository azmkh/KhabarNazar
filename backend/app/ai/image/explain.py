"""Render visual attribution maps supplied by an image model as heatmaps."""

from __future__ import annotations

from pathlib import Path

from app.ai.image.preprocess import read_image, write_image


def save_attribution_heatmap(
    image_path: str | Path,
    attribution_map,
    output_path: str | Path,
    opacity: float = 0.4,
) -> Path:
    """Overlay a model-provided 2D attribution map on its source image.

    This function does not create an attribution map or analyze an image by
    itself; a validated visual model must provide the map.
    """
    try:
        import cv2
        import numpy as np
    except ImportError as exc:
        raise RuntimeError("OpenCV and NumPy are required to render heatmaps") from exc

    if not 0.0 <= opacity <= 1.0:
        raise ValueError("opacity must be between 0 and 1")
    source = read_image(image_path)
    if source is None:
        raise ValueError("Source image could not be decoded")
    attribution = np.asarray(attribution_map, dtype=np.float32)
    if attribution.ndim != 2 or attribution.size == 0 or not np.isfinite(attribution).all():
        raise ValueError("attribution_map must be a finite, non-empty 2D array")
    minimum = float(attribution.min())
    maximum = float(attribution.max())
    if maximum <= minimum:
        raise ValueError("attribution_map must contain a non-uniform signal")

    normalized = cv2.normalize(attribution, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    resized = cv2.resize(normalized, (source.shape[1], source.shape[0]), interpolation=cv2.INTER_LINEAR)
    colored = cv2.applyColorMap(resized, cv2.COLORMAP_JET)
    overlay = cv2.addWeighted(source, 1.0 - opacity, colored, opacity, 0)
    destination = Path(output_path)
    write_image(destination, overlay)
    return destination


def explain_image(image_path: str | Path, attribution_map=None, output_path: str | Path | None = None) -> dict:
    """Create a heatmap only when a model supplies an attribution array."""
    if attribution_map is None:
        return {
            "heatmap_path": None,
            "summary": "No image heatmap is available because no visual model attribution was produced.",
            "is_stub": True,
        }
    if output_path is None:
        raise ValueError("output_path is required when an attribution map is provided")
    heatmap_path = save_attribution_heatmap(image_path, attribution_map, output_path)
    return {
        "heatmap_path": str(heatmap_path),
        "summary": "Heatmap visualizes the supplied image model attribution; it does not establish whether the associated news claim is true.",
        "is_stub": False,
    }
