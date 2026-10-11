"""Validate and resize an image dataset without touching the originals.

Reads every image under dataset/raw/images (sub-folders, e.g. one per class
such as authentic/ and manipulated/, are preserved) and writes resized copies
to dataset/processed/images. Unreadable or unsupported files are reported and
skipped. No labels are inferred; folder names are kept exactly as they are.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ai.image.preprocess import SUPPORTED_EXTENSIONS, preprocess_image

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def preprocess_folder(source_dir: Path, output_dir: Path, max_dimension: int = 1024) -> dict[str, object]:
    if not source_dir.is_dir():
        raise ValueError(f"Image folder not found: {source_dir}")
    if output_dir.resolve().is_relative_to(source_dir.resolve()):
        raise ValueError("Output folder must not be inside the raw image folder")

    processed: Counter[str] = Counter()
    skipped: list[tuple[str, str]] = []
    for path in sorted(p for p in source_dir.rglob("*") if p.is_file()):
        relative = path.relative_to(source_dir)
        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            skipped.append((str(relative), "unsupported extension"))
            continue
        try:
            preprocess_image(path, output_dir / relative, max_dimension=max_dimension)
        except (ValueError, OSError) as exc:
            skipped.append((str(relative), str(exc)))
            continue
        processed[relative.parts[0] if len(relative.parts) > 1 else "(root)"] += 1
    return {"processed_per_folder": dict(processed), "skipped": skipped}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input-dir", type=Path, default=PROJECT_ROOT / "dataset" / "raw" / "images")
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "dataset" / "processed" / "images")
    parser.add_argument("--max-dimension", type=int, default=1024)
    args = parser.parse_args()

    result = preprocess_folder(args.input_dir, args.output_dir, args.max_dimension)
    print(f"Processed images per folder: {result['processed_per_folder']}")
    print(f"Skipped {len(result['skipped'])} file(s)")
    for name, reason in result["skipped"]:
        print(f"  {name}: {reason}")


if __name__ == "__main__":
    main()
