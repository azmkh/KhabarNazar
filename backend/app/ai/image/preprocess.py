"""Basic image validation and resizing; this does not assess authenticity."""

import logging
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def _cv2():
    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError("OpenCV is required for image preprocessing; install backend requirements") from exc
    return cv2


def read_image(path: str | Path):
    """Decode an image with OpenCV. Unlike cv2.imread, this works with non-ASCII
    (e.g. Urdu) file paths on Windows. Returns None if it cannot be decoded."""
    import numpy as np

    cv2 = _cv2()
    try:
        data = np.fromfile(str(path), dtype=np.uint8)
    except OSError:
        return None
    if data.size == 0:
        return None
    return cv2.imdecode(data, cv2.IMREAD_COLOR)


def write_image(path: str | Path, image) -> None:
    """Encode and save an image; Unicode-safe counterpart of cv2.imwrite."""
    cv2 = _cv2()
    destination = Path(path)
    ok, encoded = cv2.imencode(destination.suffix or ".png", image)
    if not ok:
        raise OSError(f"Could not encode image for {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    encoded.tofile(str(destination))


def preprocess_image(
    image_path: str | Path,
    output_path: str | Path,
    max_dimension: int = 1024,
) -> Path:
    """Decode, resize while preserving aspect ratio, and save an image.

    Raises ValueError for unsupported or invalid files. Pixels are not altered
    beyond resizing; no manipulation or claim-veracity prediction is made.
    """
    cv2 = _cv2()

    source = Path(image_path)
    destination = Path(output_path)
    if source.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported image extension: {source.suffix or '(none)'}")
    if max_dimension <= 0:
        raise ValueError("max_dimension must be positive")

    image = read_image(source)
    if image is None:
        raise ValueError("Image could not be decoded")
    height, width = image.shape[:2]
    scale = min(1.0, max_dimension / max(width, height))
    if scale < 1.0:
        image = cv2.resize(
            image,
            (max(1, round(width * scale)), max(1, round(height * scale))),
            interpolation=cv2.INTER_AREA,
        )

    write_image(destination, image)
    return destination


EXIF_ORIENTATION = 0x0112


@contextmanager
def upright_image(image_path: str | Path) -> Iterator[str]:
    """Yield a path to the image as people see it (EXIF rotation applied).

    Phone cameras often store pixels sideways with an EXIF "Orientation" tag. Pillow and
    EasyOCR's colour loader ignore the tag while OpenCV applies it, so OCR, the image detector
    and the heatmap could each see a different orientation. When the tag asks for a rotation, a
    temporary upright PNG copy (lossless) is made and deleted afterwards; the stored upload is
    never changed. Images without the tag are passed through untouched.
    """
    temporary: Optional[str] = None
    try:
        from PIL import Image, ImageOps

        with Image.open(image_path) as img:
            if img.getexif().get(EXIF_ORIENTATION, 1) not in (None, 1):
                upright = ImageOps.exif_transpose(img)
                handle, temporary = tempfile.mkstemp(prefix="khabarnazar-upright-", suffix=".png")
                os.close(handle)
                upright.save(temporary, format="PNG")
    except Exception:
        logger.exception("Could not apply the EXIF orientation; using the image as stored")
        if temporary:
            Path(temporary).unlink(missing_ok=True)
        temporary = None
    try:
        yield temporary or str(image_path)
    finally:
        if temporary:
            Path(temporary).unlink(missing_ok=True)
