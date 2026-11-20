"""Every valid image goes through OCR *and* the image detector with Grad-CAM.

OCR decides only whether there is a news claim to classify; it never decides whether the
picture is analysed. These tests cover the image scenarios one by one.

Mocked tests (the default) replace EasyOCR, the XLM-R checkpoints and the image detector with
stand-ins, but keep the real language routing, persistence, heatmap rendering and API. The
tests marked real_models at the end load the real models (`pytest --real-models`).
"""
import io
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

import app.ai.pipeline as pipeline
import app.services.submission_service as submission_service
from app.ai.image import ai_detector
from app.ai.image import predict as image_predict
from app.ai.text import xlmr
from app.ai.text.language_detection import detect_language
from app.config import settings
from app.main import app
from tests.test_text_routing import FakeXlmr

client = TestClient(app)
FIXTURES = Path(__file__).resolve().parent / "fixtures"

URDU_TEXT = "حکومت نے پیٹرول کی قیمت میں پانچ روپے کمی کا اعلان کر دیا"
ROMAN_URDU_TEXT = "Hukumat ne elaan kiya hai ke kal se tamam schools band rahenge"
ENGLISH_TEXT = "The government said that all schools will be closed from tomorrow"
# EasyOCR's output for a Roman Urdu meme on the first PC: stray Urdu digits and few function words.
ROMAN_MEME_OCR = "aisa chatak\nchaanta marungi\n٨٥\n1\nchakri ki\ntarah agli diwali\ntak ghumega\nsamiha na"


def _headers(email: str) -> dict:
    response = client.post("/auth/register", json={"name": "Grad-CAM Tester", "email": email, "password": "Password123!"})
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _png(size=(320, 240), color=(90, 140, 200)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    return buf.getvalue()


def _upload(headers, data=None):
    return client.post("/submissions/image", headers=headers, files={"file": ("x.png", _png() if data is None else data, "image/png")})


def _ocr_reading(text):
    """Stand-in EasyOCR result; the language comes from the real detector, as in ocr.run_ocr."""
    def run_ocr(path):
        return {"text": text, "confidence": 0.9 if text else None,
                "language": detect_language(text) if text else None, "is_stub": False,
                "status": "completed" if text else "no_text_found", "message": None}
    return run_ocr


class Detector:
    """Stand-in for analyze_image that records which file it saw and returns a Grad-CAM map."""

    def __init__(self, p_ai=0.8, attribution=True, gradcam_error=None):
        self.p_ai, self.attribution, self.gradcam_error, self.paths = p_ai, attribution, gradcam_error, []

    def __call__(self, path):
        self.paths.append(path)
        attribution_map = np.linspace(0, 1, 64, dtype=np.float32).reshape(8, 8) if self.attribution else None
        return {"image_score": self.p_ai, "manipulation_prediction": ai_detector.label_for(1 - self.p_ai),
                "is_stub": False, "status": "completed", "summary": "stand-in detector",
                "attribution_map": attribution_map,
                "gradcam_status": "completed" if self.attribution else "failed",
                "gradcam_error": None if self.attribution else (self.gradcam_error or "no Grad-CAM map was produced"),
                "model_version": "test-detector"}


@pytest.fixture
def text_models(monkeypatch):
    urdu, roman = FakeXlmr("xlmr-urdu", 256), FakeXlmr("xlmr-roman-urdu", 512)
    monkeypatch.setattr(xlmr, "get_classifier", lambda script: ({"urdu": urdu, "roman": roman}[script], None))
    return urdu, roman


@pytest.fixture
def detector(monkeypatch):
    stand_in = Detector()
    monkeypatch.setattr(pipeline, "analyze_image", stand_in)
    return stand_in


def _heatmap_file(data) -> Path:
    return Path(settings.UPLOAD_DIR).resolve() / data["explainability"]["heatmap_path"]


def _assert_gradcam_completed(data, headers):
    assert data["gradcam_status"] == "completed"
    assert data["explainability"]["heatmap_path"] == f"explanations/{data['id']}_heatmap.png"
    assert _heatmap_file(data).is_file()
    served = client.get(f"/submissions/{data['id']}/heatmap", headers=headers)
    assert served.status_code == 200 and served.headers["content-type"] == "image/png"


# ─── Scenario 1: image with Urdu text ────────────────────────────────────────

def test_urdu_text_image_runs_ocr_text_model_image_model_and_gradcam(monkeypatch, text_models, detector):
    urdu, roman = text_models
    monkeypatch.setattr(pipeline, "run_ocr", _ocr_reading(URDU_TEXT))
    headers = _headers("s1.urdu@example.com")
    data = _upload(headers).json()
    image = data["image_submission"]

    assert image["ocr_status"] == "completed" and image["ocr_text"] == URDU_TEXT
    assert image["detected_language"] == "urdu" and urdu.calls >= 1 and roman.calls == 0
    assert image["text_classification_status"] == "completed" and image["text_prediction"] == "Real"
    assert len(detector.paths) == 1 and image["image_analysis_status"] == "completed"
    assert image["image_score"] == pytest.approx(0.8)
    _assert_gradcam_completed(data, headers)
    # Evaluation: the verdict and risk come from the text; the image score is reported beside it.
    assert data["final_label"] == "Real" and data["combined_risk_score"] == pytest.approx(0.2)
    summary = data["explainability"]["explanation_summary"]
    assert "checked as the news claim" in summary and "stand-in detector" in summary and "Grad-CAM" in summary


# ─── Scenario 2: image with Roman Urdu text ──────────────────────────────────

@pytest.mark.parametrize("ocr_text", [ROMAN_URDU_TEXT, ROMAN_MEME_OCR])
def test_roman_urdu_text_image_runs_both_paths(monkeypatch, text_models, detector, ocr_text):
    urdu, roman = text_models
    monkeypatch.setattr(pipeline, "run_ocr", _ocr_reading(ocr_text))
    headers = _headers(f"s2.roman{len(ocr_text)}@example.com")
    data = _upload(headers).json()
    image = data["image_submission"]

    assert image["detected_language"] == "roman_urdu" and roman.calls >= 1 and urdu.calls == 0
    assert image["text_classification_status"] == "completed"
    assert data["final_label"] in {"Real", "Fake"} and data["combined_risk_score"] is not None
    assert len(detector.paths) == 1 and image["image_analysis_status"] == "completed"
    _assert_gradcam_completed(data, headers)


# ─── Scenario 3: image with English text ─────────────────────────────────────

def test_english_text_image_is_classified_by_the_roman_model_and_still_gets_gradcam(monkeypatch, text_models, detector):
    urdu, roman = text_models
    monkeypatch.setattr(pipeline, "run_ocr", _ocr_reading(ENGLISH_TEXT))
    headers = _headers("s3.english@example.com")
    data = _upload(headers).json()
    image = data["image_submission"]

    # English has no model of its own: the Roman Urdu model reads it, and the result says so.
    assert image["detected_language"] == "english" and roman.calls >= 1 and urdu.calls == 0
    assert image["text_classification_status"] == "completed" and image["text_confidence"] is not None
    assert "results for English text are less reliable" in data["explainability"]["explanation_summary"]
    assert data["final_label"] in {"Real", "Fake"} and data["combined_risk_score"] is not None
    assert len(detector.paths) == 1 and image["image_analysis_status"] == "completed"
    _assert_gradcam_completed(data, headers)


# ─── Scenario 4: image with no text ──────────────────────────────────────────

def test_image_without_text_skips_classification_but_gets_image_analysis_and_gradcam(monkeypatch, text_models, detector):
    urdu, roman = text_models
    monkeypatch.setattr(pipeline, "run_ocr", _ocr_reading(None))
    headers = _headers("s4.notext@example.com")
    data = _upload(headers).json()
    image = data["image_submission"]

    assert image["ocr_status"] == "no_text_found" and image["ocr_text"] is None
    assert image["text_classification_status"] == "not_run" and urdu.calls == roman.calls == 0
    assert image["analysis_branch"] == "ai_or_real" and len(detector.paths) == 1
    _assert_gradcam_completed(data, headers)
    assert data["final_label"] == "Uncertain" and data["combined_risk_score"] is None
    assert "no fake-news verdict" in data["explainability"]["explanation_summary"]


# ─── Scenario 5: OCR failure ─────────────────────────────────────────────────

def test_ocr_failure_is_recorded_and_gradcam_still_runs(detector):
    # The conftest makes EasyOCR fail to load, as it would without its weights.
    headers = _headers("s5.ocrfail@example.com")
    data = _upload(headers).json()
    image = data["image_submission"]

    assert image["ocr_status"] == "unavailable" and image["ocr_text"] is None
    assert image["text_classification_status"] == "not_run"
    assert len(detector.paths) == 1
    _assert_gradcam_completed(data, headers)
    assert "OCR could not process this image" in data["explainability"]["explanation_summary"]
    assert data["final_label"] == "Uncertain"


# ─── Scenario 6: Grad-CAM failure ────────────────────────────────────────────

def test_gradcam_failure_keeps_text_and_image_results_without_a_heatmap(monkeypatch, text_models):
    stand_in = Detector(p_ai=0.3, attribution=False, gradcam_error="Grad-CAM could not be computed for this image")
    monkeypatch.setattr(pipeline, "analyze_image", stand_in)
    monkeypatch.setattr(pipeline, "run_ocr", _ocr_reading(ROMAN_URDU_TEXT))
    data = _upload(_headers("s6.gradcam@example.com")).json()
    image = data["image_submission"]

    assert image["text_classification_status"] == "completed" and data["final_label"] in {"Real", "Fake"}
    assert image["image_analysis_status"] == "completed" and image["image_score"] == pytest.approx(0.3)
    assert data["gradcam_status"] == "unavailable" and data["explainability"]["heatmap_path"] is None
    assert "Grad-CAM heatmap unavailable: Grad-CAM could not be computed" in data["explainability"]["explanation_summary"]


def test_heatmap_render_failure_is_reported_and_leaves_no_file(monkeypatch, text_models, detector):
    def broken_render(*args, **kwargs):
        raise ValueError("disk full")

    monkeypatch.setattr(submission_service, "explain_image", broken_render)
    monkeypatch.setattr(pipeline, "run_ocr", _ocr_reading(URDU_TEXT))
    explanations = Path(settings.UPLOAD_DIR).resolve() / "explanations"
    before = set(explanations.glob("*")) if explanations.is_dir() else set()
    response = _upload(_headers("s6.render@example.com"))
    assert response.status_code == 201
    data = response.json()
    assert data["final_label"] == "Real" and data["image_submission"]["image_score"] == pytest.approx(0.8)
    assert data["gradcam_status"] == "unavailable" and data["explainability"]["heatmap_path"] is None
    assert "heatmap image could not be rendered" in data["explainability"]["explanation_summary"]
    after = set(explanations.glob("*")) if explanations.is_dir() else set()
    assert after == before  # no heatmap file was written for this submission


def test_detector_keeps_its_prediction_when_the_gradcam_backward_pass_fails():
    torch = pytest.importorskip("torch")
    from torchvision import models

    stand_in = ai_detector.AIImageDetector.__new__(ai_detector.AIImageDetector)
    stand_in.torch = torch
    stand_in.resnet = models.resnet18(weights=None, num_classes=2).eval()
    x = torch.rand(1, 3, 224, 224)

    # The second argument is CLIP's + DINOv2's P(real); 1.0 keeps the ensemble near ResNet18's own call.
    p_ok, cam, error, explained = stand_in._resnet_with_gradcam(x, 1.0)
    assert error is None and cam.shape == (7, 7) and 0 <= p_ok <= 1 and explained in ai_detector.CLASSES

    def fail(*args):
        raise RuntimeError("backward failed")

    stand_in.resnet.fc.register_full_backward_hook(fail)
    p_failed, cam, error, _ = stand_in._resnet_with_gradcam(x, 1.0)
    assert cam is None and "Grad-CAM could not be computed" in error
    assert p_failed == pytest.approx(p_ok)            # the prediction itself is unchanged
    assert not stand_in.resnet.layer4[-1]._forward_hooks  # the Grad-CAM hook is always removed


def test_analyze_image_reports_a_missing_gradcam_map(monkeypatch, tmp_path):
    class NoMap:
        def analyse(self, img):
            return {"p_real": 0.7, "members": {}, "attribution_map": None,
                    "gradcam_error": "Grad-CAM could not be computed for this image"}

    monkeypatch.setattr(ai_detector, "load_detector", lambda: (NoMap(), None))
    path = tmp_path / "x.png"
    path.write_bytes(_png())
    result = image_predict.analyze_image(str(path))
    assert result["is_stub"] is False and result["image_score"] == pytest.approx(0.3)
    assert result["gradcam_status"] == "failed" and result["attribution_map"] is None
    assert "Grad-CAM could not be computed" in result["gradcam_error"]


# ─── Scenario 7: image-model failure ─────────────────────────────────────────

def test_image_model_failure_keeps_the_ocr_text_result(monkeypatch, text_models):
    class Broken:
        def analyse(self, img):
            raise RuntimeError("out of memory")

    monkeypatch.setattr(ai_detector, "load_detector", lambda: (Broken(), None))
    monkeypatch.setattr(pipeline, "run_ocr", _ocr_reading(URDU_TEXT))
    data = _upload(_headers("s7.imagefail@example.com")).json()
    image = data["image_submission"]

    assert image["text_classification_status"] == "completed" and data["final_label"] == "Real"
    assert image["image_analysis_status"] == "unavailable" and image["image_score"] is None
    assert image["manipulation_prediction"] == "Not Analyzed: model unavailable"
    assert data["gradcam_status"] == "not_run" and data["explainability"]["heatmap_path"] is None
    assert "detector failed on this image" in data["explainability"]["explanation_summary"]


def test_text_pipeline_failure_keeps_the_image_result(monkeypatch, detector):
    def broken_predict(text, language=None):
        raise RuntimeError("tokenizer crashed")

    monkeypatch.setattr(pipeline, "predict_text", broken_predict)
    monkeypatch.setattr(pipeline, "run_ocr", _ocr_reading(URDU_TEXT))
    headers = _headers("s7.textfail@example.com")
    data = _upload(headers).json()
    assert data["image_submission"]["text_classification_status"] == "unavailable"
    assert data["final_label"] == "Uncertain" and data["combined_risk_score"] is None
    assert "text classifier failed" in data["explainability"]["explanation_summary"]
    _assert_gradcam_completed(data, headers)


# ─── Scenario 8: invalid image ───────────────────────────────────────────────

@pytest.mark.parametrize("payload", [b"not an image at all", b"", _png()[:40]], ids=["garbage", "empty", "truncated"])
def test_invalid_image_is_rejected_before_any_model_runs(monkeypatch, payload):
    calls = []
    monkeypatch.setattr(pipeline, "run_ocr", lambda path: calls.append(("ocr", path)))
    monkeypatch.setattr(pipeline, "analyze_image", lambda path: calls.append(("image", path)))
    response = _upload(_headers(f"s8.invalid{len(payload)}@example.com"), payload)
    assert response.status_code in {400, 413, 415, 422}
    assert calls == []


# ─── Scenario 9: the result belongs to this submission ───────────────────────

def test_each_heatmap_is_made_from_its_own_upload_and_owner(monkeypatch, text_models, detector):
    monkeypatch.setattr(pipeline, "run_ocr", _ocr_reading(None))
    alice, bob = _headers("s9.alice@example.com"), _headers("s9.bob@example.com")
    first = _upload(alice, _png((300, 200), (200, 30, 30))).json()
    second = _upload(alice, _png((260, 180), (30, 200, 30))).json()
    other = _upload(bob, _png((200, 300), (30, 30, 200))).json()

    # The detector saw the stored original of each upload, not a shared or earlier file.
    stored = [str(Path(settings.UPLOAD_DIR).resolve() / d["image_submission"]["image_path"]) for d in (first, second, other)]
    assert detector.paths == stored and len(set(stored)) == 3
    # Each heatmap is drawn over its own image (same size) and named after its own submission.
    for data, size in ((first, (300, 200)), (second, (260, 180)), (other, (200, 300))):
        assert data["explainability"]["heatmap_path"] == f"explanations/{data['id']}_heatmap.png"
        with Image.open(_heatmap_file(data)) as heatmap:
            assert heatmap.size == size
    # The detail endpoint returns this submission, and other users cannot read it or its heatmap.
    detail = client.get(f"/submissions/{second['id']}", headers=alice).json()
    assert detail["id"] == second["id"] and detail["image_submission"]["image_path"] == second["image_submission"]["image_path"]
    assert client.get(f"/submissions/{second['id']}/heatmap", headers=bob).status_code == 404
    history = client.get("/submissions", headers=alice).json()
    assert [row["id"] for row in history][:2] == [second["id"], first["id"]]


# ─── Real models (pytest --real-models) ──────────────────────────────────────

def _latin_text_image(lines) -> bytes:
    img = Image.new("RGB", (1000, 400), "white")
    draw = ImageDraw.Draw(img)
    for i, line in enumerate(lines):
        draw.text((30, 30 + i * 90), line, fill="black", font_size=60)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _photo_like() -> bytes:
    rng = np.random.default_rng(0)
    gradient = np.linspace(0, 255, 640, dtype=np.float32)
    pixels = np.stack([np.tile(gradient, (480, 1)), np.tile(gradient[::-1], (480, 1)), np.full((480, 640), 120.0)], -1)
    pixels = np.clip(pixels + rng.normal(0, 12, pixels.shape), 0, 255).astype(np.uint8)
    buf = io.BytesIO()
    Image.fromarray(pixels).save(buf, format="PNG")
    return buf.getvalue()


REAL_CASES = {
    # urdu_headline.png was rendered with Windows' text engine, which shapes Urdu correctly.
    "urdu": (lambda: (FIXTURES / "urdu_headline.png").read_bytes(), "urdu", "completed"),
    "roman_urdu": (lambda: _latin_text_image(["Hukumat ne elaan kiya hai", "ke kal se tamam schools", "band rahenge"]),
                   "roman_urdu", "completed"),
    "english": (lambda: _latin_text_image(["The government said that", "all schools will be closed", "from tomorrow"]),
                "english", "completed"),
    "no_text": (_photo_like, None, "not_run"),
}


@pytest.mark.real_models
@pytest.mark.parametrize("name", list(REAL_CASES))
def test_real_models_run_ocr_and_gradcam_on_every_image(name):
    make_payload, language, text_status = REAL_CASES[name]
    headers = _headers(f"real.{name}@example.com")
    response = _upload(headers, make_payload())
    assert response.status_code == 201, response.text
    data = response.json()
    image = data["image_submission"]

    assert image["detected_language"] == language
    assert image["text_classification_status"] == text_status
    if text_status == "completed":
        assert image["text_prediction"] in {"Real", "Fake"} and data["final_label"] == image["text_prediction"]
    else:
        assert data["final_label"] == "Uncertain" and data["combined_risk_score"] is None
    assert image["image_analysis_status"] == "completed" and 0 <= image["image_score"] <= 1
    assert image["manipulation_prediction"] in {"Likely AI-generated", "Likely real photo"}
    _assert_gradcam_completed(data, headers)


# ─── Orientation and the analysed region ─────────────────────────────────────

def _sideways_jpeg(size=(400, 200)) -> bytes:
    """Pixels stored landscape with EXIF Orientation 6, so people see it portrait (200x400)."""
    img = Image.new("RGB", size, (200, 60, 60))
    ImageDraw.Draw(img).rectangle((0, 0, 60, 60), fill=(20, 20, 20))
    exif = img.getexif()
    exif[0x0112] = 6
    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif)
    return buf.getvalue()


def test_upright_image_applies_exif_rotation_and_cleans_up(tmp_path):
    from app.ai.image.preprocess import upright_image

    rotated = tmp_path / "phone.jpg"
    rotated.write_bytes(_sideways_jpeg())
    with upright_image(rotated) as path:
        assert path != str(rotated)
        with Image.open(path) as img:
            assert img.size == (200, 400)
    assert not Path(path).exists()                 # the temporary copy is removed
    assert rotated.read_bytes() == _sideways_jpeg()  # the stored upload is never changed

    plain = tmp_path / "plain.png"
    plain.write_bytes(_png())
    with upright_image(plain) as path:
        assert path == str(plain)                  # no tag: passed through untouched


def test_ocr_detector_and_heatmap_all_see_the_upright_photo(monkeypatch, text_models):
    seen = {}

    def ocr(path):
        with Image.open(path) as img:
            seen["ocr"] = img.size
        return _ocr_reading(None)(path)

    stand_in = Detector()

    def analyze(path):
        with Image.open(path) as img:
            seen["detector"] = img.size
        return stand_in(path)

    monkeypatch.setattr(pipeline, "run_ocr", ocr)
    monkeypatch.setattr(pipeline, "analyze_image", analyze)
    data = _upload(_headers("exif.rotated@example.com"), _sideways_jpeg()).json()
    assert seen == {"ocr": (200, 400), "detector": (200, 400)}
    with Image.open(_heatmap_file(data)) as heatmap:
        assert heatmap.size == (200, 400)
    assert not Path(stand_in.paths[0]).exists()  # the upright copy was temporary
    assert (Path(settings.UPLOAD_DIR).resolve() / data["image_submission"]["image_path"]).is_file()


def test_heatmap_colours_only_the_analysed_region(tmp_path):
    from app.ai.image.explain import save_attribution_heatmap

    source = tmp_path / "source.png"
    Image.new("RGB", (400, 200), (120, 120, 120)).save(source)
    output = tmp_path / "heatmap.png"
    save_attribution_heatmap(source, np.linspace(0, 1, 64).reshape(8, 8), output, region=(0.25, 0.25, 0.75, 0.75))
    with Image.open(output) as heatmap:
        pixels = np.asarray(heatmap.convert("RGB")).astype(int)
    assert (pixels[:30, :80] == 120).all()                         # outside the region: untouched
    assert np.abs(pixels[90:110, 180:220] - 120).max() > 30          # inside: coloured by the map
    assert (pixels[50, 120:280] == 255).all() or (pixels[50, 120:280] == 0).all()  # outlined edge
    with pytest.raises(ValueError):
        save_attribution_heatmap(source, np.linspace(0, 1, 64).reshape(8, 8), output, region=(0.5, 0, 0.4, 1))


def test_detector_reports_the_centre_crop_it_analysed():
    assert ai_detector.AIImageDetector.analysed_region((683, 512)) == pytest.approx(
        (230 / 683, 144 / 512, 454 / 683, 368 / 512))
    assert ai_detector.AIImageDetector.analysed_region((224, 224)) == (0.0, 0.0, 1.0, 1.0)


# ─── Grad-CAM explains the class the ensemble shows (regression for the audit's mismatch) ─────

def _stub_detector(p_clip_real, p_dino_real, resnet_bias_fake_real):
    """An AIImageDetector with stand-in CLIP/DINOv2 heads and a small random ResNet18 whose
    output is pinned by its final-layer bias, so members can be made to disagree."""
    torch = pytest.importorskip("torch")
    from types import SimpleNamespace
    from torch import nn
    from torchvision import models, transforms

    class Head:
        def __init__(self, p_real):
            self.p_real = p_real

        def predict_proba(self, features):
            return np.array([[1 - self.p_real, self.p_real]])

    torch.manual_seed(0)
    resnet = models.resnet18(weights=None)
    resnet.fc = nn.Linear(resnet.fc.in_features, 2)
    with torch.no_grad():
        resnet.fc.weight.mul_(0.01)
        resnet.fc.bias.copy_(torch.tensor(resnet_bias_fake_real, dtype=torch.float32))
    detector = ai_detector.AIImageDetector.__new__(ai_detector.AIImageDetector)
    detector.torch = torch
    detector.resnet = resnet.eval()
    detector.clip = lambda pixel_values: SimpleNamespace(image_embeds=torch.zeros(1, 768))
    detector.dino = lambda pixel_values: SimpleNamespace(pooler_output=torch.zeros(1, 1024))
    detector.clip_head, detector.dino_head = Head(p_clip_real), Head(p_dino_real)
    pipe = lambda mean, std: transforms.Compose([transforms.CenterCrop(224), transforms.ToTensor(), transforms.Normalize(mean, std)])
    detector.imagenet_tf = pipe(ai_detector.IMAGENET_MEAN, ai_detector.IMAGENET_STD)
    detector.clip_tf = pipe(ai_detector.CLIP_MEAN, ai_detector.CLIP_STD)
    return detector


def _noise_image():
    rng = np.random.default_rng(0)
    return Image.fromarray(rng.integers(0, 255, (480, 640, 3), dtype=np.uint8))


def test_gradcam_explains_the_ensemble_label_when_resnet_disagrees():
    # ResNet18 alone says AI-generated (P(real) ~ 0), CLIP and DINOv2 say real: the ensemble shows "real".
    result = _stub_detector(0.95, 0.95, (6.0, -6.0)).analyse(_noise_image())
    assert result["members"]["resnet18_robust"] < 0.01
    assert result["p_real"] == pytest.approx((0.95 + 0.95 + result["members"]["resnet18_robust"]) / 3)
    assert ai_detector.label_for(result["p_real"]) == ai_detector.LABEL_REAL      # the ensemble label is unchanged
    assert result["gradcam_class"] == "real"                                      # the heatmap explains that label
    assert result["gradcam_resnet_agrees"] is False
    assert result["attribution_map"] is not None


def test_gradcam_target_follows_the_ensemble_not_resnet():
    image = _noise_image()
    shown_real = _stub_detector(0.95, 0.95, (6.0, -6.0)).analyse(image)
    shown_fake = _stub_detector(0.05, 0.05, (6.0, -6.0)).analyse(image)
    assert (shown_real["gradcam_class"], shown_fake["gradcam_class"]) == ("real", "fake")
    assert shown_fake["gradcam_resnet_agrees"] is True
    # Same image and ResNet18, different explained class: the maps must differ.
    assert not np.allclose(shown_real["attribution_map"], shown_fake["attribution_map"])


def test_analyze_image_reports_the_explained_class(monkeypatch, tmp_path):
    detector = _stub_detector(0.95, 0.95, (6.0, -6.0))
    monkeypatch.setattr(ai_detector, "load_detector", lambda: (detector, None))
    path = tmp_path / "x.png"
    _noise_image().save(path)
    result = image_predict.analyze_image(str(path))
    assert result["manipulation_prediction"] == ai_detector.LABEL_REAL
    assert result["gradcam_class"] == "real" and result["gradcam_status"] == "completed"
    assert "trained on camera photos" in result["summary"]


def test_no_heatmap_when_resnet_has_no_evidence_for_the_shown_label_says_why(monkeypatch):
    # When ResNet18 is near-certain of the other class its map for the shown class is flat:
    # no heatmap is invented, and the reason says why.
    detector = _stub_detector(0.95, 0.95, (6.0, -6.0))
    monkeypatch.setattr(detector, "_place_in_image", lambda cam, size: None)
    result = detector.analyse(_noise_image())
    assert result["attribution_map"] is None and result["gradcam_class"] == "real"
    assert "leaned strongly the other way" in result["gradcam_error"]
