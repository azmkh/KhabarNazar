"""The text and image pipelines from the project diagram, with mocked models.

Mocked tests replace OCR, the text classifier or the image detector with stand-ins, so they
check routing, persistence and honesty of the results, not model quality. The smoke tests at
the end load the real models and only run with `pytest --real-models`.
"""
import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

import app.ai.pipeline as pipeline
from app.ai.image import ai_detector
from app.ai.image import predict as image_predict
from app.main import app

client = TestClient(app)

URDU_TEXT = "حکومت نے پیٹرول کی قیمت میں پانچ روپے کمی کا اعلان کر دیا"
ROMAN_URDU_TEXT = "Hukumat ne elaan kiya hai ke kal se tamam schools band rahenge."


def _headers(email: str) -> dict:
    response = client.post("/auth/register", json={"name": "Pipeline Tester", "email": email, "password": "Password123!"})
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _image_bytes(fmt: str = "PNG", size=(64, 48)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, (90, 140, 200)).save(buf, format=fmt)
    return buf.getvalue()


def _upload(headers, data=None, name="x.png", mime="image/png"):
    return client.post("/submissions/image", headers=headers, files={"file": (name, data or _image_bytes(), mime)})


def _ocr(text, confidence=0.9, status="completed", language="urdu"):
    return {"text": text, "confidence": confidence, "language": language if text else None,
            "is_stub": False, "status": status, "message": None}


def _classifier(prediction="Fake", p_fake=0.85):
    calls = []

    def predict(text, language=None):
        calls.append(text)
        return {"prediction": prediction, "confidence": max(p_fake, 1 - p_fake), "fake_probability": p_fake,
                "summary": f"stand-in classifier said {prediction}", "model_version": "test-text", "is_stub": False}

    return predict, calls


def _detector(p_ai=0.9):
    calls = []

    def analyze(path):
        calls.append(path)
        return {"image_score": p_ai, "manipulation_prediction": ai_detector.label_for(1 - p_ai), "is_stub": False,
                "status": "completed", "summary": "stand-in detector", "attribution_map": None,
                "model_version": "test-detector"}

    return analyze, calls


@pytest.fixture
def no_explanations(monkeypatch):
    monkeypatch.setattr(
        pipeline,
        "explain_text",
        lambda text, **kwargs: {"highlighted_words": [], "summary": "explained", "is_stub": False},
    )


# ─── Text pipeline ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("text", ["", "  ", "\n\t \n", "ab"])
def test_blank_or_too_short_text_is_rejected(text):
    response = client.post("/submissions/text", json={"text": text}, headers=_headers(f"blank{len(text)}{text.count(' ')}@example.com"))
    assert response.status_code == 422


def test_malformed_text_payloads_are_rejected():
    headers = _headers("malformed.text@example.com")
    assert client.post("/submissions/text", json={"txt": "missing field"}, headers=headers).status_code == 422
    assert client.post("/submissions/text", json={"text": 12345}, headers=headers).status_code == 422
    assert client.post("/submissions/text", json={"text": "x" * 10_001}, headers=headers).status_code == 422


def test_unexpected_characters_do_not_break_classification():
    response = client.post("/submissions/text", json={"text": "😀 <script>alert(1)</script> ​ ۔۔۔ ؟"},
                           headers=_headers("odd.chars@example.com"))
    assert response.status_code == 201
    assert response.json()["final_label"] == "Uncertain"  # no model in tests: nothing is invented


@pytest.mark.parametrize(
    ("text", "language"),
    [
        ("Yeh khabar sach hai ya jhoot, kya aap ko pata hai?", "roman_urdu"),
        ("The report was released on Monday and we reviewed it.", "english"),
        ("Headline from Lahore", "unknown"),
        ("وزیر اعظم نے کہا prime minister", "mixed"),
    ],
)
def test_unavailable_language_models_are_explicit(text, language):
    headers = _headers(f"unavailable.{language}@example.com")
    response = client.post("/submissions/text", json={"text": text}, headers=headers)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["detected_language"] == language
    assert body["final_label"] == "Uncertain"
    assert body["combined_risk_score"] is None
    assert body["text_submission"]["text_confidence"] is None
    assert body["text_submission"]["processing_status"] == "unavailable"
    assert body["explainability"]["explanation_summary"]


def test_text_verdict_and_risk_come_from_the_classifier(monkeypatch, no_explanations):
    predict, calls = _classifier("Fake", 0.85)
    monkeypatch.setattr(pipeline, "predict_text", predict)
    data = client.post("/submissions/text", json={"text": URDU_TEXT}, headers=_headers("text.verdict@example.com")).json()
    assert calls == [URDU_TEXT]
    assert data["final_label"] == "Fake"
    assert data["combined_risk_score"] == pytest.approx(0.85)
    assert data["text_submission"]["text_confidence"] == pytest.approx(0.85)


# ─── Image pipeline: routing between the two branches ────────────────────────

def test_image_with_text_becomes_an_image_pair(monkeypatch, no_explanations):
    predict, text_calls = _classifier("Fake", 0.8)
    analyze, detector_calls = _detector()
    monkeypatch.setattr(pipeline, "run_ocr", lambda path: _ocr(URDU_TEXT))
    monkeypatch.setattr(pipeline, "predict_text", predict)
    monkeypatch.setattr(pipeline, "analyze_image", analyze)

    headers = _headers("pair@example.com")
    data = _upload(headers).json()
    image = data["image_submission"]
    assert image["analysis_branch"] == "image_pair"
    # The pair keeps the image, the extracted text and the text classification together.
    assert image["image_path"] and image["ocr_text"] == URDU_TEXT and image["text_prediction"] == "Fake"
    assert text_calls == [URDU_TEXT]           # the same text pipeline as typed text
    assert detector_calls == []                 # an image with text skips the AI-or-real detector
    assert image["manipulation_prediction"] == "Skipped: image has text" and image["image_score"] is None
    assert data["final_label"] == "Fake" and data["combined_risk_score"] == pytest.approx(0.8)

    stored = client.get(f"/submissions/{data['id']}", headers=headers).json()
    assert stored["image_submission"]["ocr_text"] == URDU_TEXT


def test_ocr_text_uses_the_same_classifier_as_typed_text(monkeypatch, no_explanations):
    predict, calls = _classifier("Real", 0.1)
    monkeypatch.setattr(pipeline, "predict_text", predict)
    monkeypatch.setattr(pipeline, "run_ocr", lambda path: _ocr(URDU_TEXT))
    headers = _headers("same.classifier@example.com")
    typed = client.post("/submissions/text", json={"text": URDU_TEXT}, headers=headers).json()
    from_image = _upload(headers).json()
    assert calls == [URDU_TEXT, URDU_TEXT]
    assert typed["final_label"] == from_image["final_label"] == "Real"
    assert typed["combined_risk_score"] == from_image["combined_risk_score"]


def test_image_without_text_goes_to_ai_or_real_and_gets_no_news_verdict(monkeypatch):
    predict, text_calls = _classifier()
    analyze, detector_calls = _detector(p_ai=0.97)
    monkeypatch.setattr(pipeline, "run_ocr", lambda path: _ocr(None, None, "no_text_found"))
    monkeypatch.setattr(pipeline, "predict_text", predict)
    monkeypatch.setattr(pipeline, "analyze_image", analyze)

    data = _upload(_headers("no.text@example.com")).json()
    image = data["image_submission"]
    assert image["analysis_branch"] == "ai_or_real"
    assert len(detector_calls) == 1 and text_calls == []
    assert image["image_score"] == pytest.approx(0.97)
    assert image["manipulation_prediction"] == "Likely AI-generated"
    # An AI-generated picture is not evidence that a claim is fake.
    assert data["final_label"] == "Uncertain" and data["combined_risk_score"] is None
    assert "no fake-news verdict" in data["explainability"]["explanation_summary"]


@pytest.mark.parametrize("ocr_result", [
    _ocr("ab", 0.95),                     # a few stray letters (logo, watermark)
    _ocr(URDU_TEXT, 0.1),                  # plenty of text, but read with very low confidence
])
def test_unreadable_or_ambiguous_text_is_not_classified(monkeypatch, ocr_result):
    predict, text_calls = _classifier()
    analyze, detector_calls = _detector(p_ai=0.2)
    monkeypatch.setattr(pipeline, "run_ocr", lambda path: ocr_result)
    monkeypatch.setattr(pipeline, "predict_text", predict)
    monkeypatch.setattr(pipeline, "analyze_image", analyze)

    data = _upload(_headers(f"ambiguous{ocr_result['confidence']}@example.com")).json()
    assert data["image_submission"]["analysis_branch"] == "ai_or_real"
    assert text_calls == [] and len(detector_calls) == 1
    assert data["image_submission"]["manipulation_prediction"] == "Likely real photo"
    assert data["final_label"] == "Uncertain"
    assert "too little to check" in data["explainability"]["explanation_summary"]


def test_ocr_failure_is_reported_and_the_picture_is_still_checked(monkeypatch):
    analyze, detector_calls = _detector()
    monkeypatch.setattr(pipeline, "analyze_image", analyze)
    # The conftest makes EasyOCR fail to load, as it would without its weights.
    data = _upload(_headers("ocr.failure@example.com")).json()
    assert data["image_submission"]["ocr_text"] is None
    assert data["image_submission"]["analysis_branch"] == "ai_or_real" and len(detector_calls) == 1
    assert "OCR could not process this image" in data["explainability"]["explanation_summary"]
    assert data["final_label"] == "Uncertain"


def test_image_model_unavailable_is_explicit():
    # No image model folder in tests, and OCR is unavailable: nothing is invented.
    data = _upload(_headers("no.image.model@example.com")).json()
    image = data["image_submission"]
    assert image["analysis_branch"] == "ai_or_real"
    assert image["image_score"] is None
    assert image["manipulation_prediction"] == "Not Analyzed: model unavailable"
    assert data["explainability"]["model_version"] == "image-model-unavailable"
    assert "not analyzed" in data["explainability"]["explanation_summary"].lower()
    assert data["final_label"] == "Uncertain" and data["combined_risk_score"] is None


def test_text_in_image_that_the_text_model_cannot_classify_stays_uncertain(monkeypatch):
    # Roman Urdu OCR text with no Roman Urdu model: an image pair, but no invented prediction.
    monkeypatch.setattr(pipeline, "run_ocr", lambda path: _ocr("Yeh khabar bilkul jhoot hai", 0.9, language="roman_urdu"))
    data = _upload(_headers("pair.unavailable@example.com")).json()
    assert data["image_submission"]["analysis_branch"] == "image_pair"
    assert data["image_submission"]["text_prediction"] == "Uncertain"
    assert data["final_label"] == "Uncertain" and data["combined_risk_score"] is None
    assert "could not be classified" in data["explainability"]["explanation_summary"]


# ─── Upload validation ───────────────────────────────────────────────────────

def test_corrupted_image_is_rejected():
    noise = Image.frombytes("RGB", (120, 120), bytes(range(256)) * 168 + bytes(192))
    buf = io.BytesIO()
    noise.save(buf, format="PNG")
    data = bytearray(buf.getvalue())
    data[300:700] = b"\x00" * 400            # valid header, damaged pixel data
    response = _upload(_headers("corrupt@example.com"), bytes(data))
    assert response.status_code == 415


def test_unsupported_image_type_is_rejected_whatever_the_header_says():
    response = _upload(_headers("gif@example.com"), _image_bytes("GIF"), "pic.png", "image/png")
    assert response.status_code == 415


def test_decompression_bomb_sized_image_is_rejected(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "MAX_IMAGE_PIXELS", 1000)
    response = _upload(_headers("bomb@example.com"), _image_bytes("PNG", (100, 100)))
    assert response.status_code == 413


# ─── Image detector unit checks (no torch needed) ────────────────────────────

def test_label_mapping_and_score_direction(monkeypatch, tmp_path):
    assert ai_detector.CLASSES[ai_detector.REAL_INDEX] == "real"
    assert ai_detector.label_for(0.5) == "Likely real photo"
    assert ai_detector.label_for(0.49) == "Likely AI-generated"

    class StandIn:
        def analyse(self, img):
            return {"p_real": 0.25, "members": {"clip_vitl14": 0.2, "dinov2_l": 0.3, "resnet18_robust": 0.25},
                    "attribution_map": None}

    monkeypatch.setattr(ai_detector, "load_detector", lambda: (StandIn(), None))
    path = tmp_path / "label.png"
    path.write_bytes(_image_bytes())
    result = image_predict.analyze_image(str(path))
    assert result["image_score"] == pytest.approx(0.75)  # image_score = P(AI-generated) = 1 - P(real)
    assert result["manipulation_prediction"] == "Likely AI-generated"
    assert "not whether any news claim is true" in result["summary"]


def test_detector_failure_is_reported(monkeypatch, tmp_path):
    class Broken:
        def analyse(self, img):
            raise RuntimeError("out of memory")

    monkeypatch.setattr(ai_detector, "load_detector", lambda: (Broken(), None))
    path = tmp_path / "x.png"
    path.write_bytes(_image_bytes())
    result = image_predict.analyze_image(str(path))
    assert result["image_score"] is None and result["is_stub"] is True


def test_preprocessing_matches_the_notebooks():
    big = ai_detector.standardise(Image.new("L", (2000, 1000)))
    assert big.mode == "RGB" and big.size == (1024, 512)          # shorter side to 512
    small = ai_detector.standardise(Image.new("RGB", (300, 100)))
    assert small.size == (672, 224)                                 # never below 224
    kept = ai_detector.standardise(Image.new("RGB", (400, 300)))
    assert kept.size == (400, 300)                                  # between 224 and 512: unchanged
    assert ai_detector.crop_box((1024, 512)) == (400, 144, 624, 368)


# ─── Real models (pytest --real-models) ──────────────────────────────────────

def _text_image(lines) -> bytes:
    img = Image.new("RGB", (900, 300), "white")
    draw = ImageDraw.Draw(img)
    for i, line in enumerate(lines):
        draw.text((30, 40 + i * 90), line, fill="black", font_size=60)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.mark.real_models
def test_real_urdu_text_model():
    from app.ai.text.predict import predict_text

    result = predict_text(URDU_TEXT)
    assert result["is_stub"] is False and result["prediction"] in {"Fake", "Real"}
    assert 0 <= result["fake_probability"] <= 1


@pytest.mark.real_models
def test_real_urdu_text_submission_returns_and_persists_model_result():
    headers = _headers("real.urdu.model@example.com")
    response = client.post("/submissions/text", json={"text": URDU_TEXT}, headers=headers)
    assert response.status_code == 201, response.text
    created = response.json()
    text_result = created["text_submission"]
    assert created["detected_language"] == "urdu"
    assert text_result["processing_status"] == "completed"
    assert text_result["text_prediction"] in {"Fake", "Real"}
    assert 0 <= text_result["text_confidence"] <= 1

    detail = client.get(f"/submissions/{created['id']}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["text_submission"]["text_prediction"] == text_result["text_prediction"]
    assert detail.json()["explainability"]["model_version"] == "text-xlmr-hookbait"


@pytest.mark.real_models
def test_real_long_urdu_article_uses_the_long_article_model(monkeypatch):
    from app.config import settings

    # Use text_module/urdu's real file instead of the hidden path conftest sets.
    monkeypatch.delenv("KHABARNAZAR_TEXT_MODEL_PATH", raising=False)
    monkeypatch.setattr(settings, "TEXT_MODEL_PATH", None)
    headers = _headers("real.urdu.article@example.com")
    long_text = " ".join([URDU_TEXT] * 20)
    response = client.post("/submissions/text", json={"text": long_text}, headers=headers)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["final_label"] in {"Fake", "Real"}
    assert 0 <= body["combined_risk_score"] <= 1
    assert body["explainability"]["model_version"] == "tfidf-urdu-long-articles"
    assert "long-article Urdu model" in body["explainability"]["explanation_summary"]


@pytest.mark.real_models
def test_real_urdu_text_over_model_limit_uses_training_truncation():
    # The long-article model file is hidden here (conftest), so the XLM-R fallback is tested.
    headers = _headers("real.urdu.long@example.com")
    long_text = " ".join([URDU_TEXT] * 20)
    response = client.post("/submissions/text", json={"text": long_text}, headers=headers)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["final_label"] in {"Fake", "Real"}
    assert body["combined_risk_score"] is not None
    assert body["text_submission"]["processing_status"] == "completed"
    assert body["text_submission"]["text_confidence"] is not None
    assert "truncated to 64 model tokens" in body["explainability"]["explanation_summary"]


@pytest.mark.real_models
def test_real_roman_urdu_model_routes_and_predicts():
    from app.ai.text.predict import predict_text

    result = predict_text(ROMAN_URDU_TEXT)
    assert result["detected_language"] == "roman_urdu"
    assert result["model_version"] == "xlmr-roman-urdu"
    assert result["is_stub"] is False and result["prediction"] in {"Fake", "Real"}
    assert 0 <= result["fake_probability"] <= 1


@pytest.mark.real_models
def test_real_roman_submission_persists_and_returns_history():
    headers = _headers("real.roman.model@example.com")
    response = client.post("/submissions/text", json={"text": ROMAN_URDU_TEXT}, headers=headers)
    assert response.status_code == 201, response.text
    created = response.json()
    assert created["detected_language"] == "roman_urdu"
    assert created["text_submission"]["processing_status"] == "completed"
    assert created["text_submission"]["text_prediction"] in {"Fake", "Real"}
    assert 0 <= created["text_submission"]["text_confidence"] <= 1
    detail = client.get(f"/submissions/{created['id']}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["text_submission"]["text_prediction"] == created["text_submission"]["text_prediction"]
    assert detail.json()["explainability"]["model_version"] == "xlmr-roman-urdu"


@pytest.mark.real_models
def test_roman_urdu_over_512_tokens_is_truncated_at_trained_limit():
    from app.ai.text.predict import predict_text

    result = predict_text(" ".join([ROMAN_URDU_TEXT] * 80))
    assert result["detected_language"] == "roman_urdu"
    assert result["prediction"] in {"Fake", "Real"} and result["is_stub"] is False
    assert result["input_truncated"] is True
    assert result["input_token_count"] > result["max_input_tokens"] == 512


@pytest.mark.real_models
def test_real_image_detector(tmp_path):
    path = tmp_path / "photo.png"
    path.write_bytes(_image_bytes("PNG", (800, 600)))
    result = image_predict.analyze_image(str(path))
    assert result["is_stub"] is False
    assert 0 <= result["image_score"] <= 1
    assert result["manipulation_prediction"] in {"Likely AI-generated", "Likely real photo"}
    assert result["attribution_map"].shape == (512, 683)  # 800x600 -> shorter side 512


@pytest.mark.real_models
def test_real_ocr_routes_text_image_to_image_pair(tmp_path):
    from app.ai.image.ocr import run_ocr

    path = tmp_path / "text.png"
    path.write_bytes(_text_image(["Breaking news today", "Prices fall sharply"]))
    ocr = run_ocr(str(path))
    assert ocr["status"] == "completed" and "news" in ocr["text"].lower()
    assert pipeline.run_image_pipeline(str(path))["branch"] == "image_pair"
