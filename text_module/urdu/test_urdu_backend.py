"""Test the Urdu fake-news detection exactly as the backend runs it.

Uses backend/app/ai/text (predict_text + explain_text), so it checks the
routing (short Urdu -> XLM-R, long Urdu -> TF-IDF) and the real models.
No database or server is needed.

Run from the repo root, in an environment with torch, transformers and
scikit-learn 1.9.1 (e.g. khabarnazar-env):

    python text_module/urdu/test_urdu_backend.py
    python text_module/urdu/test_urdu_backend.py --text "your Urdu news here"
    python text_module/urdu/test_urdu_backend.py --data E:/KhabarNazar/urdu_text/data/processed --n 1000
"""
import argparse
import sys
import time
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "backend"))

from app.ai.text.explain import explain_text  # noqa: E402
from app.ai.text.predict import LONG_TEXT_WORDS, predict_text  # noqa: E402

EXAMPLES = [
    "پاکستان اسٹاک ایکسچینج میں کاروبار کا مثبت دن",
    "ایک دہائی پرانے ویڈیو کو مدینہ شریف کا حالیہ ویڈیو بتا کر وائرل کیا جا رہا ہے",
    "وزیر اعظم نے آج قومی اسمبلی میں بجٹ پیش کیا",
]


def show(text: str) -> None:
    result = predict_text(text)
    explanation = explain_text(text, top_k=5)
    words = ", ".join(f"{h['word']} ({h['contribution']:+.2f})" for h in explanation["highlighted_words"])
    print(f"\n{text[:90]}{'...' if len(text) > 90 else ''}")
    print(f"  -> {result['prediction']}  confidence {result['confidence']}  "
          f"fake_probability {result['fake_probability']}  model {result['model_version']}")
    print(f"  top words: {words or '-'}")


def evaluate(csv_path: Path, n: int) -> None:
    import pandas as pd
    from sklearn.metrics import accuracy_score, f1_score

    df = pd.read_csv(csv_path)
    if n and len(df) > n:
        df = df.sample(n, random_state=42)
    start = time.time()
    results = [predict_text(t) for t in df["text"]]
    preds = [1 if r["prediction"] == "Fake" else 0 for r in results]
    models = Counter(r["model_version"] for r in results)
    print(f"\n{csv_path.name}: {len(df)} rows in {time.time() - start:.0f}s | models used: {dict(models)}")
    print(f"  accuracy {accuracy_score(df['label'], preds):.4f} | "
          f"macro-F1 {f1_score(df['label'], preds, average='macro'):.4f}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--text", help="classify one Urdu text and exit")
    parser.add_argument("--data", default="E:/KhabarNazar/urdu_text/data/processed",
                        help="folder with hab_test.csv / a2g_test.csv / fire_test.csv from the notebook")
    parser.add_argument("--n", type=int, default=500, help="rows per test file (0 = all)")
    args = parser.parse_args()

    if args.text:
        show(args.text)
        return

    print(f"Urdu inputs over {LONG_TEXT_WORDS} words go to the TF-IDF model, shorter ones to XLM-R.")
    print("\n=== Example sentences ===")
    for text in EXAMPLES:
        show(text)

    print("\n=== Test sets (expected: Hook and Bait ~0.97, FIRE ~0.6) ===")
    data = Path(args.data)
    for name in ["hab_test.csv", "a2g_test.csv", "fire_test.csv"]:
        if (data / name).is_file():
            evaluate(data / name, args.n)
        else:
            print(f"\n{name}: not found in {data} (skipped)")


if __name__ == "__main__":
    main()
