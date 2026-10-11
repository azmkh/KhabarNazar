"""Inspect and prepare Excel datasets without assuming column names.

Pipeline: load -> validate columns -> drop empty rows -> normalize text ->
drop empty labels -> remove duplicates -> save processed copy -> split.
The source workbook is only read, never modified.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd

from app.ai.text.preprocess import normalize_text

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATASET_DIR = PROJECT_ROOT / "dataset"


def inspect_excel(path: Path) -> list[dict[str, object]]:
    """Return workbook sheet names, columns, and row counts without data values."""
    workbook = pd.ExcelFile(path, engine="openpyxl")
    result = []
    for sheet in workbook.sheet_names:
        frame = pd.read_excel(workbook, sheet_name=sheet)
        result.append({"sheet": sheet, "rows": len(frame), "columns": list(frame.columns)})
    return result


def _require_column(frame: pd.DataFrame, column: str, kind: str) -> None:
    if column not in frame.columns:
        raise ValueError(f"{kind} column {column!r} not found; columns are {list(frame.columns)!r}")


def clean_frame(
    frame: pd.DataFrame,
    text_column: str | None = None,
    label_column: str | None = None,
) -> tuple[pd.DataFrame, dict[str, int]]:
    """Clean an already-loaded sheet and report how many rows each step removed."""
    report: dict[str, int] = {"loaded": len(frame)}
    frame = frame.dropna(how="all").copy()
    report["empty_rows_removed"] = report["loaded"] - len(frame)

    if text_column is not None:
        _require_column(frame, text_column, "Text")
        frame[text_column] = frame[text_column].map(normalize_text)
        before = len(frame)
        frame = frame[frame[text_column].ne("")].copy()
        report["empty_text_removed"] = before - len(frame)

    if label_column is not None:
        _require_column(frame, label_column, "Label")
        labels = frame[label_column].map(lambda value: "" if pd.isna(value) else str(value).strip())
        before = len(frame)
        frame = frame[labels.ne("")].copy()
        frame[label_column] = labels[labels.ne("")]
        report["empty_label_removed"] = before - len(frame)

    before = len(frame)
    if text_column is not None and label_column is not None:
        # The same text with different labels cannot be learned; drop all copies of it.
        label_counts = frame.groupby(text_column)[label_column].nunique()
        conflicting = set(label_counts[label_counts > 1].index)
        frame = frame[~frame[text_column].isin(conflicting)]
        report["conflicting_label_texts_removed"] = len(conflicting)
        frame = frame.drop_duplicates(subset=[text_column])
    elif text_column is not None:
        frame = frame.drop_duplicates(subset=[text_column])
    else:
        frame = frame.drop_duplicates()
    report["duplicate_or_conflicting_rows_removed"] = before - len(frame)
    report["kept"] = len(frame)
    return frame.reset_index(drop=True), report


def load_and_clean_excel(
    path: Path,
    sheet_name: str | int = 0,
    text_column: str | None = None,
    label_column: str | None = None,
) -> pd.DataFrame:
    """Load a sheet and clean it (see clean_frame)."""
    frame = pd.read_excel(path, sheet_name=sheet_name, engine="openpyxl")
    cleaned, _ = clean_frame(frame, text_column, label_column)
    return cleaned


def split_dataset(
    frame: pd.DataFrame,
    output_dir: Path,
    label_column: str | None = None,
    test_size: float = 0.2,
    validation_size: float = 0.1,
    random_state: int = 42,
) -> dict[str, int]:
    """Write reproducible CSV splits, stratified by label when a label column is given."""
    if len(frame) < 3:
        raise ValueError("At least 3 valid rows are needed to create train/validation/test splits")
    if not 0 < test_size < 1 or not 0 < validation_size < 1 or test_size + validation_size >= 1:
        raise ValueError("test_size and validation_size must be positive and sum to less than 1")
    if label_column is not None:
        _require_column(frame, label_column, "Label")

    from sklearn.model_selection import train_test_split

    def stratify_on(part: pd.DataFrame):
        # Stratifying needs at least 2 rows of every label; otherwise fall back to random.
        if label_column is None or part[label_column].value_counts().min() < 2:
            return None
        return part[label_column]

    try:
        rest, test = train_test_split(
            frame, test_size=test_size, random_state=random_state, stratify=stratify_on(frame)
        )
        validation_share = validation_size / (1 - test_size)
        train, validation = train_test_split(
            rest, test_size=validation_share, random_state=random_state, stratify=stratify_on(rest)
        )
    except ValueError as exc:
        raise ValueError(f"Could not split {len(frame)} rows: {exc}. Use more data or smaller split ratios.") from exc

    splits = {"train": train, "validation": validation, "test": test}
    for name, split in splits.items():
        split_directory = output_dir / name
        split_directory.mkdir(parents=True, exist_ok=True)
        split.to_csv(split_directory / f"{name}.csv", index=False, encoding="utf-8-sig")
    return {name: len(split) for name, split in splits.items()}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("input", type=Path, help="Path to an .xlsx workbook")
    parser.add_argument("--sheet", default="0", help="Sheet name or zero-based index (default: 0)")
    parser.add_argument("--text-column", help="Column to normalize, de-duplicate, and filter when empty")
    parser.add_argument("--label-column", help="Existing label column; empty labels are removed and splits are stratified")
    parser.add_argument("--inspect", action="store_true", help="Print workbook metadata only")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_DATASET_DIR)
    args = parser.parse_args()
    if args.inspect:
        for sheet in inspect_excel(args.input):
            print(f"{sheet['sheet']}: {sheet['rows']} rows; columns={sheet['columns']}")
        return

    sheet: str | int = int(args.sheet) if args.sheet.isdigit() else args.sheet
    frame = pd.read_excel(args.input, sheet_name=sheet, engine="openpyxl")
    cleaned, report = clean_frame(frame, args.text_column, args.label_column)
    for step, count in report.items():
        print(f"  {step}: {count}")
    if args.label_column:
        print(f"  label distribution: {cleaned[args.label_column].value_counts().to_dict()}")

    processed_dir = args.output_dir / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)
    cleaned.to_csv(processed_dir / "cleaned.csv", index=False, encoding="utf-8-sig")

    counts = split_dataset(cleaned, args.output_dir, args.label_column)
    print(f"Prepared {sum(counts.values())} rows: {counts}")


if __name__ == "__main__":
    main()
