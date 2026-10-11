"""Stage 5/7: language detection, a real (tiny) trained model through the API,
and explainability. The model is trained on synthetic sentences purely to test
the plumbing; its predictions mean nothing about real news."""
import io

import joblib
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import FeatureUnion, Pipeline

from app.ai.text.language_detection import detect_language
from app.main import app

client = TestClient(app)

FAKE_WORDS = ["viral", "jhoot", "afwah", "sazish", "fake"]
REAL_WORDS = ["sarkari", "elaan", "report", "tasdeeq", "official"]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("وزیر اعظم نے آج ایک بیان جاری کیا۔", "urdu"),
        ("Yeh khabar sach hai ya jhoot, kya aap ko pata hai?", "roman_urdu"),
        ("The minister said that the report was released on Monday.", "english"),
        ("وزیر اعظم نے کہا prime minister", "mixed"),
        ("12345 !!!", "unknown"),
    ],
)
def test_detect_language(text, expected):
    assert detect_language(text) == expected


@pytest.fixture
def trained_model(tmp_path, monkeypatch):
    texts, labels = [], []
    for i in range(30):
        texts.append(f"{FAKE_WORDS[i % 5]} {FAKE_WORDS[(i + 1) % 5]} khabar {i}")
        labels.append("1")
        texts.append(f"{REAL_WORDS[i % 5]} {REAL_WORDS[(i + 2) % 5]} khabar {i}")
        labels.append("0")
    pipeline = Pipeline([
        ("features", FeatureUnion([
            ("word", TfidfVectorizer(analyzer="word")),
            ("character", TfidfVectorizer(analyzer="char", ngram_range=(2, 4))),
        ])),
        ("classifier", LogisticRegression(max_iter=1000)),
    ])
    pipeline.fit(texts, labels)
    path = tmp_path / "text_classifier.joblib"
    joblib.dump({"model": pipeline, "label_map": {"1": "Fake", "0": "Real"}, "model_version": "test-model"}, path)
    monkeypatch.setenv("KHABARNAZAR_TEXT_MODEL_PATH", str(path))
    return path


def _token(email: str) -> dict:
    response = client.post("/auth/register", json={"name": "Model Tester", "email": email, "password": "Password123!"})
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_trained_model_prediction_risk_and_highlights(trained_model):
    headers = _token("model.user@example.com")

    fake = client.post("/submissions/text", json={"text": "viral jhoot afwah"}, headers=headers)
    assert fake.status_code == 201, fake.text
    fake = fake.json()
    assert fake["final_label"] == "Fake"
    assert fake["text_submission"]["text_confidence"] > 0.5
    # Risk is the probability of Fake, so for a Fake prediction it equals confidence.
    assert fake["combined_risk_score"] == pytest.approx(fake["text_submission"]["text_confidence"])
    assert fake["explainability"]["model_version"] == "test-model"
    assert '"word"' in fake["explainability"]["highlighted_words"]

    real = client.post("/submissions/text", json={"text": "sarkari elaan official"}, headers=headers).json()
    assert real["final_label"] == "Real"
    # A confident "Real" must have LOW risk (previously risk = confidence, i.e. high).
    assert real["combined_risk_score"] < 0.5
    assert real["combined_risk_score"] == pytest.approx(1 - real["text_submission"]["text_confidence"], abs=1e-3)


def test_image_submission_uses_ocr_text_with_trained_model(trained_model, monkeypatch):
    import app.services.submission_service as service

    monkeypatch.setattr(service, "run_ocr", lambda path: {
        "text": "viral jhoot afwah", "confidence": 0.9, "language": "roman_urdu",
        "is_stub": False, "status": "completed", "message": None,
    })
    buf = io.BytesIO()
    Image.new("RGB", (8, 8)).save(buf, format="PNG")
    data = client.post(
        "/submissions/image",
        headers=_token("model.image@example.com"),
        files={"file": ("x.png", buf.getvalue(), "image/png")},
    ).json()
    assert data["final_label"] == "Fake"
    assert data["image_submission"]["text_prediction"] == "Fake"
    # No image model: the manipulation signal stays empty and is not mixed into the risk.
    assert data["image_submission"]["image_score"] is None
    assert data["combined_risk_score"] == pytest.approx(data["image_submission"]["text_confidence"])
    assert data["explainability"]["highlighted_words"]


def test_corrupt_model_file_falls_back_instead_of_crashing(tmp_path, monkeypatch):
    broken = tmp_path / "broken.joblib"
    broken.write_bytes(b"not a model")
    monkeypatch.setenv("KHABARNAZAR_TEXT_MODEL_PATH", str(broken))
    response = client.post(
        "/submissions/text",
        json={"text": "viral jhoot afwah"},
        headers=_token("model.broken@example.com"),
    )
    assert response.status_code == 201
    assert response.json()["final_label"] == "Uncertain"
    assert response.json()["explainability"]["model_version"] == "text-model-unavailable"


def test_combined_risk_weighting(monkeypatch):
    from app.config import settings
    from app.services.submission_service import _build_combined_risk

    monkeypatch.setattr(settings, "TEXT_RISK_WEIGHT", 0.7)
    monkeypatch.setattr(settings, "IMAGE_RISK_WEIGHT", 0.3)
    assert _build_combined_risk(None, None) is None
    assert _build_combined_risk(0.8, None) == 0.8
    assert _build_combined_risk(None, 0.4) == 0.4
    assert _build_combined_risk(1.0, 0.0) == 0.7
