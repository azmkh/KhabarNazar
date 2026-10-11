"""
Image upload utility: validation, secure renaming, and storage.

Security measures applied:
- File type validated via magic bytes (Pillow), NOT just extension or Content-Type header
- Filename sanitized — original name is never trusted
- UUID-based filename prevents guessing and collisions
- Path traversal prevented by using Path.resolve()
- File size enforced before writing to disk
"""
import os
import uuid
from pathlib import Path
from typing import Tuple

from fastapi import HTTPException, UploadFile, status
from PIL import Image as PILImage

from app.config import settings

# Build absolute upload directory path
UPLOAD_DIR = Path(settings.UPLOAD_DIR).resolve()
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Maximum file size in bytes
MAX_BYTES = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024

# Extension map for supported MIME types
MIME_TO_EXT: dict[str, str] = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


def _detect_image_mime(data: bytes) -> str:
    """
    Detect MIME type from raw bytes using Pillow — independent of HTTP headers.
    Returns one of the allowed MIME types or raises HTTPException.
    """
    import io
    try:
        img = PILImage.open(io.BytesIO(data))
        fmt = (img.format or "").lower()
        # open() only reads the header; verify() checks the file is not truncated/corrupt.
        img.verify()
        mapping = {"jpeg": "image/jpeg", "jpg": "image/jpeg", "png": "image/png", "webp": "image/webp"}
        mime = mapping.get(fmt)
        if not mime:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=f"Unsupported image format '{fmt}'. Accepted: JPEG, PNG, WEBP.",
            )
        return mime
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="File does not appear to be a valid image.",
        )


def save_upload(upload: UploadFile) -> Tuple[str, str, int, str]:
    """
    Validates, renames, and saves an uploaded image file.

    Returns:
        Tuple of (relative_path, original_filename, file_size_bytes, detected_mime_type)

    Raises:
        HTTPException 415 if MIME type is unsupported.
        HTTPException 413 if file exceeds size limit.
    """
    # Read at most one byte more than the limit so oversized uploads are never fully loaded.
    raw = upload.file.read(MAX_BYTES + 1)
    file_size = len(raw)

    if file_size > MAX_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File is larger than the maximum allowed size of {settings.MAX_UPLOAD_SIZE_MB} MB.",
        )

    if file_size == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    # Validate image via magic bytes
    detected_mime = _detect_image_mime(raw)
    ext = MIME_TO_EXT[detected_mime]

    # Generate safe filename with UUID
    safe_name = f"{uuid.uuid4().hex}{ext}"
    dest_path = UPLOAD_DIR / safe_name

    # Safety check against path traversal (defense in depth)
    if not dest_path.resolve().is_relative_to(UPLOAD_DIR):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file path.",
        )

    with open(dest_path, "wb") as f:
        f.write(raw)

    # Kept for display only; never used to build a path.
    original_filename = Path(upload.filename or "upload").name[:255]
    relative_path = safe_name  # stored relative to UPLOAD_DIR

    return relative_path, original_filename, file_size, detected_mime


def delete_upload(relative_path: str) -> None:
    """Remove a stored upload, e.g. when analysis fails after the file was saved."""
    path = (UPLOAD_DIR / relative_path).resolve()
    if path.is_relative_to(UPLOAD_DIR) and path.is_file():
        path.unlink()
