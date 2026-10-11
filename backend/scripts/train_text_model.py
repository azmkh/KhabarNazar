"""Train and evaluate a real Fake/Real Urdu/Roman Urdu text classifier."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import joblib
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, f1_score
from sklearn.pipeline import FeatureUnion, Pipeline

from app.ai.text.preprocess import normalize_text

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def load_split(path: Path, text_column: str, label_column: str) -> pd.DataFrame:
    # Read labels as text so numeric labels (0/1) match the --fake-label/--real-label strings.
    frame = pd.read_csv(path, dtype={label_column: str}, encoding="utf-8-sig")
    missing = {text_column, label_column} - set(frame.columns)
    if missing:
        raise ValueError(f"{path} is missing requested columns: {sorted(missing)}")
    frame = frame[[text_column, label_column]].dropna().copy()
    frame[label_column] = frame[label_column].str.strip()
    frame[text_column] = frame[text_column].map(normalize_text)
    frame = frame[frame[text_column].ne("")]
    if frame.empty:
        raise ValueError(f"{path} has no non-empty labeled rows")
    return frame


def evaluate(name: str, model: Pipeline, frame: pd.DataFrame, text_column: str, label_column: str) -> dict:
    expected = frame[label_column].astype(str)
    predicted = model.predict(frame[text_column].tolist())
    metrics = {
        "accuracy": round(float(accuracy_score(expected, predicted)), 4),
        "macro_f1": round(float(f1_score(expected, predicted, average="macro", zero_division=0)), 4),
        "rows": len(frame),
    }
    print(f"{name}: accuracy={metrics['accuracy']:.4f}; macro_f1={metrics['macro_f1']:.4f}")
    print(classification_report(expected, predicted, zero_division=0))
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train", type=Path, default=PROJECT_ROOT / "dataset" / "train" / "train.csv")
    parser.add_argument("--validation", type=Path, default=PROJECT_ROOT / "dataset" / "validation" / "validation.csv")
    parser.add_argument("--test", type=Path, default=PROJECT_ROOT / "dataset" / "test" / "test.csv")
    parser.add_argument("--text-column", required=True, help="Exact text column name from the workbook")
    parser.add_argument("--label-column", required=True, help="Exact existing binary label column name")
    parser.add_argument("--fake-label", required=True, help="Exact dataset value representing Fake")
    parser.add_argument("--real-label", required=True, help="Exact dataset value representing Real")
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "models" / "text" / "text_classifier.joblib")
    args = parser.parse_args()
    if args.fake_label == args.real_label:
        parser.error("--fake-label and --real-label must be different")

    train = load_split(args.train, args.text_column, args.label_column)
    validation = load_split(args.validation, args.text_column, args.label_column)
    test = load_split(args.test, args.text_column, args.label_column)
    accepted_labels = {args.fake_label, args.real_label}
    for split_name, frame in (("train", train), ("validation", validation), ("test", test)):
        found = set(frame[args.label_column].astype(str))
        if not found <= accepted_labels:
            raise ValueError(f"{split_name} contains labels not mapped by --fake-label/--real-label: {sorted(found - accepted_labels)}")
    if set(train[args.label_column].astype(str)) != accepted_labels:
        raise ValueError("Training data must contain examples for both the configured Fake and Real labels")

    features = FeatureUnion([
        ("word", TfidfVectorizer(analyzer="word", ngram_range=(1, 2), min_df=1, sublinear_tf=True)),
        ("character", TfidfVectorizer(analyzer="char", ngram_range=(2, 5), min_df=1, sublinear_tf=True)),
    ])
    classifier = Pipeline([
        ("features", features),
        ("classifier", LogisticRegression(max_iter=1000, class_weight="balanced", random_state=42)),
    ])
    train_labels = train[args.label_column].astype(str)
    classifier.fit(train[args.text_column].tolist(), train_labels)
    validation_metrics = evaluate("Validation", classifier, validation, args.text_column, args.label_column)
    test_metrics = evaluate("Test", classifier, test, args.text_column, args.label_column)

    artifact = {
        "model": classifier,
        "label_map": {args.fake_label: "Fake", args.real_label: "Real"},
        "text_column": args.text_column,
        "label_column": args.label_column,
        "training_rows": len(train),
        "model_type": "word-and-character-tfidf-logistic-regression",
        "model_version": "text-tfidf-logreg",
        "metrics": {"validation": validation_metrics, "test": test_metrics},
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, args.output)
    print(f"Saved model artifact to {args.output.resolve()}")


if __name__ == "__main__":
    main()
