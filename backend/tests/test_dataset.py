"""Dataset preparation scripts (Stage 4). Uses synthetic data in a temp folder."""
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest
from PIL import Image

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR / "scripts"))

from preprocess_excel import clean_frame, split_dataset  # noqa: E402
from preprocess_images import preprocess_folder  # noqa: E402


def _synthetic_frame() -> pd.DataFrame:
    rows = [{"news": f"خبر نمبر {i}  ", "label": "fake" if i % 2 else "real"} for i in range(20)]
    rows += [
        {"news": None, "label": None},             # fully empty row
        {"news": "   ", "label": "fake"},          # empty text
        {"news": "label missing", "label": None},  # empty label
        {"news": "خبر نمبر 1", "label": "fake"},   # exact duplicate text + label
        {"news": "mixed", "label": "fake"},
        {"news": "mixed", "label": "real"},        # same text, conflicting labels
    ]
    return pd.DataFrame(rows)


def test_clean_frame_removes_invalid_duplicate_and_conflicting_rows():
    cleaned, report = clean_frame(_synthetic_frame(), text_column="news", label_column="label")
    assert len(cleaned) == 20
    assert report["empty_rows_removed"] == 1
    assert report["empty_text_removed"] == 1
    assert report["empty_label_removed"] == 1
    assert report["conflicting_label_texts_removed"] == 1
    assert "mixed" not in set(cleaned["news"])
    assert cleaned["news"].str.endswith(" ").sum() == 0  # whitespace normalized


def test_clean_frame_reports_missing_column():
    with pytest.raises(ValueError, match="not found"):
        clean_frame(_synthetic_frame(), text_column="does_not_exist")


def test_split_is_stratified_and_complete(tmp_path):
    cleaned, _ = clean_frame(_synthetic_frame(), text_column="news", label_column="label")
    counts = split_dataset(cleaned, tmp_path, label_column="label")
    assert sum(counts.values()) == len(cleaned)
    for split in ("train", "validation", "test"):
        frame = pd.read_csv(tmp_path / split / f"{split}.csv", encoding="utf-8-sig")
        assert set(frame["label"]) == {"fake", "real"}


def test_excel_and_training_scripts_run_end_to_end(tmp_path):
    workbook = tmp_path / "source.xlsx"
    _synthetic_frame().to_excel(workbook, index=False)
    original = workbook.read_bytes()

    prep = subprocess.run(
        [sys.executable, "scripts/preprocess_excel.py", str(workbook),
         "--text-column", "news", "--label-column", "label", "--output-dir", str(tmp_path / "dataset")],
        cwd=BACKEND_DIR, capture_output=True, text=True, encoding="utf-8",
    )
    assert prep.returncode == 0, prep.stderr
    assert workbook.read_bytes() == original  # source workbook untouched
    assert (tmp_path / "dataset" / "processed" / "cleaned.csv").is_file()

    model_path = tmp_path / "model.joblib"
    data = tmp_path / "dataset"
    train = subprocess.run(
        [sys.executable, "scripts/train_text_model.py",
         "--train", str(data / "train" / "train.csv"),
         "--validation", str(data / "validation" / "validation.csv"),
         "--test", str(data / "test" / "test.csv"),
         "--text-column", "news", "--label-column", "label",
         "--fake-label", "fake", "--real-label", "real", "--output", str(model_path)],
        cwd=BACKEND_DIR, capture_output=True, text=True, encoding="utf-8",
    )
    assert train.returncode == 0, train.stderr
    assert model_path.is_file()


def test_image_folder_preprocessing_keeps_originals_and_handles_urdu_names(tmp_path):
    raw = tmp_path / "raw"
    (raw / "authentic").mkdir(parents=True)
    Image.new("RGB", (2000, 1000), (10, 20, 30)).save(raw / "authentic" / "تصویر.png")
    (raw / "authentic" / "broken.jpg").write_bytes(b"not an image")
    (raw / "notes.txt").write_text("ignore me")
    out = tmp_path / "processed"

    result = preprocess_folder(raw, out, max_dimension=500)
    assert result["processed_per_folder"] == {"authentic": 1}
    assert len(result["skipped"]) == 2
    with Image.open(out / "authentic" / "تصویر.png") as resized:
        assert resized.size == (500, 250)
    with Image.open(raw / "authentic" / "تصویر.png") as original:
        assert original.size == (2000, 1000)
