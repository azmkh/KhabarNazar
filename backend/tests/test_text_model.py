"""Mocked routing and API persistence tests for the Urdu/Roman Urdu XLM-R service."""

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

import app.ai.text.xlmr as xlmr
from app.ai.text.language_detection import detect_language
from app.ai.text.predict import predict_text
from app.main import app
from app.schemas.submission import TextSubmissionResponse

client = TestClient(app)
URDU = "وزیر اعظم نے آج ایک بیان جاری کیا۔"
ROMAN = "Yeh khabar sach hai ya jhoot, kya aap ko pata hai?"
ENGLISH = "The report was released on Monday and we reviewed it."


class FakeClassifier:
    def __init__(self, script: str, label: str = "Fake", p_fake: float = 0.87):
        self.script = script
        self.model_version = f"mock-xlmr-{script}"
        self.label = label
        self.p_fake = p_fake
        self.max_len = 64 if script == "urdu" else 512

    def predict(self, text: str):
        return {
            "prediction": self.label,
            "confidence": max(self.p_fake, 1 - self.p_fake),
            "fake_probability": self.p_fake,
            "model_version": self.model_version,
            "is_stub": False,
            "status": "completed",
            "input_truncated": False,
            "input_token_count": 20,
            "max_input_tokens": self.max_len,
        }

    def explain(self, text: str, top_k: int = 8, max_words: int = 8, base_fake_probability=None):
        return [{"word": "khabar", "contribution": 0.2, "direction": "supports_prediction"}]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (URDU, "urdu"),
        (ROMAN, "roman_urdu"),
        (ENGLISH, "english"),
        ("وزیر اعظم نے کہا prime minister", "mixed"),
        ("Yeh news is important", "unknown"),
        ("Headline from Lahore", "unknown"),
        ("12345 !!!", "unknown"),
    ],
)
def test_detect_language(text, expected):
    assert detect_language(text) == expected


@pytest.mark.parametrize(
    ("prediction", "confidence", "expected_status"),
    [("Fake", 0.8, "completed"), ("Uncertain", None, "unavailable")],
)
def test_text_response_includes_processing_status(prediction, confidence, expected_status):
    response = TextSubmissionResponse(
        id=1,
        input_text="a submitted claim",
        detected_language="roman_urdu",
        text_prediction=prediction,
        text_confidence=confidence,
        created_at=datetime.now(timezone.utc),
    )
    assert response.processing_status == expected_status


def _auth(email: str) -> dict:
    response = client.post("/auth/register", json={
        "name": "Model Tester", "email": email, "password": "Password123!"
    })
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.mark.parametrize(("text", "script", "language"), [
    (URDU, "urdu", "urdu"), (ROMAN, "roman", "roman_urdu")
])
def test_language_routes_to_its_own_model(text, script, language, monkeypatch):
    calls = []
    classifier = FakeClassifier(script)
    monkeypatch.setattr(xlmr, "get_classifier", lambda selected: (calls.append(selected) or classifier, None))
    result = predict_text(text)
    assert calls == [script]
    assert result["detected_language"] == language
    assert result["prediction"] == "Fake" and result["is_stub"] is False
    assert result["fake_probability"] == pytest.approx(0.87)


@pytest.mark.parametrize("text", [ENGLISH, "وزیر اعظم نے کہا prime minister", "Headline from Lahore"])
def test_english_mixed_and_ambiguous_are_not_routed_to_either_model(text, monkeypatch):
    calls = []
    def no_model(script):
        calls.append(script)
        return None, "not requested"
    monkeypatch.setattr(xlmr, "get_classifier", no_model)
    result = predict_text(text)
    assert calls == []
    assert result["prediction"] == "Uncertain" and result["confidence"] is None
    assert result["is_stub"] is True


def test_missing_or_failed_model_never_returns_a_prediction(monkeypatch):
    monkeypatch.setattr(xlmr, "get_classifier", lambda script: (None, "model unavailable"))
    missing = predict_text(ROMAN)
    assert missing["prediction"] == "Uncertain" and missing["confidence"] is None

    monkeypatch.setattr(xlmr, "get_classifier", lambda script: (_ for _ in ()).throw(RuntimeError("private detail")))
    failed = predict_text(ROMAN)
    assert failed["prediction"] == "Uncertain" and failed["confidence"] is None
    assert "private detail" not in failed["summary"]


def test_inference_exception_never_returns_a_prediction(monkeypatch):
    class BrokenClassifier:
        def predict(self, text):
            raise RuntimeError("private inference detail")

    monkeypatch.setattr(xlmr, "get_classifier", lambda script: (BrokenClassifier(), None))
    result = predict_text(ROMAN)
    assert result["prediction"] == "Uncertain"
    assert result["confidence"] is None
    assert result["status"] == "unavailable"
    assert "private inference detail" not in result["summary"]


def test_authenticated_roman_result_is_persisted_and_read_back(monkeypatch):
    classifier = FakeClassifier("roman", label="Real", p_fake=0.13)
    monkeypatch.setattr(xlmr, "get_classifier", lambda script: (classifier, None))
    headers = _auth("roman.mock@example.com")
    response = client.post("/submissions/text", json={"text": ROMAN}, headers=headers)
    assert response.status_code == 201, response.text
    created = response.json()
    assert created["text_submission"]["detected_language"] == "roman_urdu"
    assert created["text_submission"]["text_prediction"] == "Real"
    assert created["text_submission"]["processing_status"] == "completed"
    assert created["combined_risk_score"] == pytest.approx(0.13)
    detail = client.get(f"/submissions/{created['id']}", headers=headers).json()
    assert detail["text_submission"]["text_prediction"] == "Real"
    assert detail["explainability"]["model_version"] == "mock-xlmr-roman"
