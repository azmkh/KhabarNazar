"""
Keeps uploads and heatmaps visible across server containers.

Locally, UPLOAD_DIR is an ordinary folder and both functions below do nothing.

On Modal, UPLOAD_DIR is a mounted Modal Volume (see modal_app.py). A container sees the Volume
as it was when the container started, and its own writes reach other containers only once they
are committed (Modal also auto-commits every few seconds and on shutdown). modal_app.py calls
`use_volume(volume)` at startup, after which:

- `persist()` commits right after an upload and its heatmap are saved, so another container
  (or the next one after scale-to-zero) can serve them straight away;
- `ensure_visible(path)` reloads the Volume once when a requested file is missing here,
  because another container may have written it after this one started.
"""
from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

_volume: Optional[Any] = None
_lock = threading.Lock()


def use_volume(volume: Any) -> None:
    """Register the mounted Modal Volume (anything with commit() and reload())."""
    global _volume
    _volume = volume


def persist() -> None:
    """Commit new files to the shared Volume; a no-op without one."""
    if _volume is None:
        return
    try:
        with _lock:
            _volume.commit()
    except Exception:
        # Modal still auto-commits shortly afterwards; the request itself succeeded.
        logger.exception("Could not commit the uploads Volume")


def ensure_visible(path: Path) -> bool:
    """True when `path` is a file, reloading the shared Volume once if it is missing."""
    if path.is_file():
        return True
    if _volume is None:
        return False
    try:
        with _lock:
            _volume.reload()
    except Exception:
        # Reload fails while another request has a Volume file open ("volume busy").
        logger.warning("Could not reload the uploads Volume to look for %s", path.name, exc_info=True)
    return path.is_file()
