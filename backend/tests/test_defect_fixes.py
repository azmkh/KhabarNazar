"""Regression tests for the defects found by the full test pass of 2026-11-24 (DEF-01 .. DEF-06).

DEF-02 is a screen change (app/result/[id].tsx); its data side (final_label_source on every
result) is covered here, the screen itself by the web UI pass.
"""
import io
import itertools
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

import app.ai.pipeline as pipeline
import app.services.submission_service as submission_service
from app.ai.text import xlmr
from app.ai.text.predict import model_language, predict_text
from app.config import settings
from app.database import SessionLocal
from app.main import app
from app.models.submission import Submission
from app.models.user import User
from tests.test_image_gradcam import Detector, _ocr_reading
from tests.test_text_routing import FakeXlmr

client = TestClient(app)
fault_client = TestClient(app, raise_server_exceptions=False)
_ids = itertools.count()


def _headers(role: str = "user") -> dict:
    email = f"defects.{role}.{next(_ids)}@example.com"
    r = client.post("/auth/register", json={"name": "Defect Tester", "email": email, "password": "Password123!"})
    if r.status_code == 400:
        r = client.post("/auth/login", json={"email": email, "password": "Password123!"})
    if role == "admin":
        db = SessionLocal()
        try:
            db.query(User).filter(User.email == email).one().role = "admin"
            db.commit()
        finally:
            db.close()
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def text_models(monkeypatch):
    urdu, roman = FakeXlmr("xlmr-urdu", 256), FakeXlmr("xlmr-roman-urdu", 512)
    monkeypatch.setattr(xlmr, "get_classifier", lambda script: ({"urdu": urdu, "roman": roman}[script], None))
    return urdu, roman


# ── DEF-01: a link alone is not text to classify ────────────────────────────

@pytest.mark.parametrize("text", [
    "https://example.com/news/2026/11/24/story-12345",
    "www.example.com/khabar",
    "  http://a.b/c  https://d.e/f  ",
    "reporter@example.com",
    "https://example.com/x 12345 !!!",
])
def test_links_only_are_uncertain_without_a_score(text, text_models):
    result = predict_text(text)
    assert result["prediction"] == "Uncertain"
    assert result["confidence"] is None and result["fake_probability"] is None
    assert "links" in result["summary"]
    assert text_models[0].calls == text_models[1].calls == 0  # no model was asked


def test_text_with_a_link_is_still_classified_on_its_words(text_models):
    assert model_language("Hukoomat ne elan kiya hai https://example.com/a", "roman_urdu") == "roman_urdu"
    result = predict_text("viral jhoot khabar hai, dekhiye https://example.com/video")
    assert result["prediction"] in ("Real", "Fake") and result["model_version"] == "xlmr-roman-urdu"


def test_link_only_submission_over_http_has_no_verdict(text_models):
    r = client.post("/submissions/text", json={"text": "https://example.com/news/2026/11/24/story-12345"}, headers=_headers())
    assert r.status_code == 201
    body = r.json()
    assert body["final_label"] == "Uncertain" and body["combined_risk_score"] is None
    assert body["text_submission"]["text_confidence"] is None


# ── DEF-04: a failing explanation keeps the classification ─────────────────

def test_explanation_failure_keeps_the_verdict(text_models, monkeypatch):
    def broken(*args, **kwargs):
        raise RuntimeError("explanation failed")

    monkeypatch.setattr(pipeline, "explain_text", broken)
    r = client.post("/submissions/text", json={"text": "viral jhoot khabar hai"}, headers=_headers())
    assert r.status_code == 201
    body = r.json()
    assert body["final_label"] in ("Real", "Fake")
    assert body["text_submission"]["text_confidence"] is not None
    assert "Detailed explanation is temporarily unavailable." in body["explainability"]["explanation_summary"]
    assert body["explainability"]["highlighted_words"] is None


# ── DEF-05: ids and offsets beyond the database integer range ───────────────

@pytest.mark.parametrize("path", [
    "/submissions/99999999999999999999", "/submissions/99999999999999999999/image",
    "/submissions/99999999999999999999/heatmap", "/disputes/99999999999999999999",
    "/submissions/0", "/submissions/-1/image", "/submissions?skip=99999999999999999999",
    "/disputes?skip=99999999999999999999",
])
def test_out_of_range_ids_are_422_not_500(path):
    r = fault_client.get(path, headers=_headers())
    assert r.status_code == 422, (path, r.status_code)


def test_out_of_range_ids_on_admin_and_write_routes():
    admin = _headers("admin")
    assert fault_client.get("/admin/submissions?skip=99999999999999999999", headers=admin).status_code == 422
    assert fault_client.patch("/disputes/99999999999999999999", headers=admin,
                              json={"admin_decision": "uphold_ai", "admin_comment": "checked"}).status_code == 422
    assert fault_client.post("/disputes", headers=_headers(),
                             json={"submission_id": 99999999999999999999, "justification": "far too large an id"}).status_code == 422


# ── DEF-03: the admin list can be filtered ──────────────────────────────────

def test_admin_list_filters_by_label_type_dispute_and_email(text_models):
    admin = _headers("admin")
    owner = _headers()
    owner_email = client.get("/users/me", headers=owner).json()["email"]
    fake_id = client.post("/submissions/text", json={"text": "viral jhoot khabar hai"}, headers=owner).json()["id"]
    real_id = client.post("/submissions/text", json={"text": "Hukoomat ne aaj naya pul khola hai"}, headers=owner).json()["id"]
    client.post("/disputes", headers=owner, json={"submission_id": fake_id, "justification": "This verdict is wrong."})

    def ids(query):
        r = client.get(f"/admin/submissions?limit=100&{query}", headers=admin)
        assert r.status_code == 200
        got = {item["id"] for item in r.json()}
        assert int(r.headers["X-Total-Count"]) >= len(got)
        return got, r.json()

    mine = f"user_email={owner_email}"
    got, rows = ids(mine)
    assert got == {fake_id, real_id} and {row["user_email"] for row in rows} == {owner_email}
    assert ids(f"{mine}&final_label=Fake")[0] == {fake_id}
    assert ids(f"{mine}&final_label=Real")[0] == {real_id}
    assert ids(f"{mine}&disputed=true")[0] == {fake_id}
    assert ids(f"{mine}&disputed=false")[0] == {real_id}
    assert ids(f"{mine}&submission_type=image")[0] == set()
    assert ids(f"user_email={owner_email.upper()}")[0] == {fake_id, real_id}  # case-insensitive
    assert client.get("/admin/submissions?user_email=%25_%25", headers=admin).headers["X-Total-Count"] == "0"
    assert client.get("/admin/submissions?final_label=Maybe", headers=admin).status_code == 422
    total_fake = client.get("/admin/submissions?final_label=Fake&limit=1", headers=admin)
    assert int(total_fake.headers["X-Total-Count"]) >= 1 and len(total_fake.json()) == 1  # total counts all pages


# ── DEF-02 (data side): the label's source is on every result ───────────────

def test_result_says_whether_the_label_is_the_ai_or_the_admin(text_models):
    owner, admin = _headers(), _headers("admin")
    sid = client.post("/submissions/text", json={"text": "viral jhoot khabar hai"}, headers=owner).json()["id"]
    assert client.get(f"/submissions/{sid}", headers=owner).json()["final_label_source"] == "AI"
    did = client.post("/disputes", headers=owner, json={"submission_id": sid, "justification": "Ministry denied this."}).json()["id"]
    client.patch(f"/disputes/{did}", headers=admin, json={"admin_decision": "override", "admin_comment": "Checked.", "override_label": "Real"})
    detail = client.get(f"/submissions/{sid}", headers=owner).json()
    assert detail["final_label"] == "Real" and detail["final_label_source"] == "Admin"
    # The AI's own verdict stays available for the screen's "AI's original estimate" line.
    assert detail["text_submission"]["text_prediction"] == "Fake"


# ── DEF-06: a failed image submission leaves no heatmap file ───────────────

def test_failed_image_submission_leaves_no_heatmap_file(text_models, monkeypatch):
    monkeypatch.setattr(pipeline, "analyze_image", Detector())
    monkeypatch.setattr(pipeline, "run_ocr", _ocr_reading(None))

    class Broken:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("saving the explanation failed")

    monkeypatch.setattr(submission_service, "Explainability", Broken)
    uploads = Path(settings.UPLOAD_DIR).resolve()
    heatmaps = uploads / "explanations"
    before_heatmaps = set(heatmaps.glob("*")) if heatmaps.exists() else set()
    before_uploads = set(uploads.glob("*.*"))
    db = SessionLocal()
    try:
        before_rows = db.query(Submission).count()
    finally:
        db.close()
    buf = io.BytesIO()
    Image.new("RGB", (320, 240), (90, 140, 200)).save(buf, format="PNG")
    r = fault_client.post("/submissions/image", headers=_headers(), files={"file": ("x.png", buf.getvalue(), "image/png")})
    assert r.status_code == 500
    # No new file stays behind. (tests/_uploads keeps files of earlier runs whose database was
    # rebuilt, so a stale file with this submission's id may have been replaced and removed.)
    assert not (set(heatmaps.glob("*")) if heatmaps.exists() else set()) - before_heatmaps
    assert not set(uploads.glob("*.*")) - before_uploads
    db = SessionLocal()
    try:
        assert db.query(Submission).count() == before_rows
    finally:
        db.close()
