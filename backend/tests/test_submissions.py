import io

from fastapi.testclient import TestClient
from PIL import Image

from app.main import app

client = TestClient(app)


def _png_bytes(size=(8, 8), color=(20, 80, 160)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color=color).save(buf, format="PNG")
    return buf.getvalue()


def _register(email: str, password: str = "Password123!", name: str = "Test User") -> str:
    response = client.post(
        "/auth/register",
        json={"name": name, "email": email, "password": password},
    )
    assert response.status_code == 201, response.text
    return response.json()["access_token"]


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_text_submission_requires_auth():
    response = client.post("/submissions/text", json={"text": "Yeh ek Roman Urdu news claim hai."})
    assert response.status_code == 401


def test_text_submission_success():
    token = _register("text.submit@example.com")
    response = client.post(
        "/submissions/text",
        json={"text": "وزیر اعظم نے آج ایک بیان جاری کیا۔"},
        headers=_auth_headers(token),
    )
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["submission_type"] == "text"
    assert data["final_label"] == "Uncertain"
    assert data["final_label_source"] == "AI"
    assert data["text_submission"]["input_text"].startswith("وزیر")
    assert data["text_submission"]["detected_language"] == "urdu"
    assert data["text_submission"]["text_prediction"] == "Uncertain"
    assert data["explainability"] is not None
    assert "password" not in data
    assert "password_hash" not in data


def test_text_submission_rejects_short_input():
    token = _register("text.short@example.com")
    response = client.post(
        "/submissions/text",
        json={"text": "hi"},
        headers=_auth_headers(token),
    )
    assert response.status_code == 422


def test_image_upload_success():
    token = _register("image.submit@example.com")
    response = client.post(
        "/submissions/image",
        headers=_auth_headers(token),
        files={"file": ("screenshot.png", _png_bytes(), "image/png")},
    )
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["submission_type"] == "image"
    assert data["image_submission"]["mime_type"] == "image/png"
    assert data["image_submission"]["original_filename"] == "screenshot.png"
    assert data["image_submission"]["file_size_bytes"] > 0
    assert data["image_submission"]["image_path"]
    assert data["image_submission"]["image_path"] != "screenshot.png"
    assert data["final_label"] == "Uncertain"
    assert data["image_submission"]["manipulation_prediction"] is not None


def test_image_upload_rejects_non_image():
    token = _register("image.bad@example.com")
    response = client.post(
        "/submissions/image",
        headers=_auth_headers(token),
        files={"file": ("notes.txt", b"this is not an image", "text/plain")},
    )
    assert response.status_code == 415


def test_image_upload_rejects_empty_file():
    token = _register("image.empty@example.com")
    response = client.post(
        "/submissions/image",
        headers=_auth_headers(token),
        files={"file": ("empty.png", b"", "image/png")},
    )
    assert response.status_code == 400


def test_submission_history_and_detail():
    token = _register("history.user@example.com")
    headers = _auth_headers(token)

    empty = client.get("/submissions", headers=headers)
    assert empty.status_code == 200
    assert empty.json() == []

    text_res = client.post(
        "/submissions/text",
        json={"text": "Roman Urdu claim about an event in Karachi."},
        headers=headers,
    )
    image_res = client.post(
        "/submissions/image",
        headers=headers,
        files={"file": ("clip.webp", _png_bytes(), "image/png")},
    )
    assert text_res.status_code == 201
    assert image_res.status_code == 201

    history = client.get("/submissions", headers=headers)
    assert history.status_code == 200
    items = history.json()
    assert len(items) == 2
    assert items[0]["id"] == image_res.json()["id"]
    assert items[1]["submission_type"] == "text"
    assert items[1]["text_preview"]
    assert items[0]["has_image"] is True

    detail = client.get(f"/submissions/{text_res.json()['id']}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["text_submission"]["input_text"].startswith("Roman Urdu")


def test_user_cannot_read_another_users_submission():
    owner_token = _register("owner.user@example.com")
    other_token = _register("other.user@example.com")
    created = client.post(
        "/submissions/text",
        json={"text": "Private submission belonging to the owner."},
        headers=_auth_headers(owner_token),
    )
    assert created.status_code == 201
    submission_id = created.json()["id"]

    response = client.get(
        f"/submissions/{submission_id}",
        headers=_auth_headers(other_token),
    )
    assert response.status_code == 404


def test_missing_submission_returns_404():
    token = _register("missing.sub@example.com")
    response = client.get("/submissions/999999", headers=_auth_headers(token))
    assert response.status_code == 404


def _make_admin(email: str) -> str:
    from app.database import SessionLocal
    from app.models.user import User

    token = _register(email)
    db = SessionLocal()
    try:
        db.query(User).filter(User.email == email).one().role = "admin"
        db.commit()
    finally:
        db.close()
    return token


def test_new_submission_fields_are_not_invented():
    token = _register("honest.fields@example.com")
    data = client.post(
        "/submissions/text",
        json={"text": "Yeh khabar sach hai ya jhoot?"},
        headers=_auth_headers(token),
    ).json()
    assert data["is_news"] is None
    assert data["combined_risk_score"] is None
    assert data["text_submission"]["text_confidence"] is None
    assert data["created_at"].endswith("Z") or data["created_at"].endswith("+00:00")


def test_image_upload_rejects_oversized_file(monkeypatch):
    import app.utils.upload as upload

    monkeypatch.setattr(upload, "MAX_BYTES", 10)
    token = _register("image.large@example.com")
    response = client.post(
        "/submissions/image",
        headers=_auth_headers(token),
        files={"file": ("big.png", _png_bytes(), "image/png")},
    )
    assert response.status_code == 413


def test_image_upload_rejects_truncated_image():
    token = _register("image.truncated@example.com")
    data = _png_bytes(size=(64, 64))
    response = client.post(
        "/submissions/image",
        headers=_auth_headers(token),
        files={"file": ("cut.png", data[: len(data) // 2], "image/png")},
    )
    assert response.status_code == 415


def test_failed_image_analysis_removes_stored_file(monkeypatch):
    from pathlib import Path

    import app.routers.submissions as submissions_router
    from app.config import settings

    def broken_analysis(**kwargs):
        raise RuntimeError("analysis failed")

    monkeypatch.setattr(submissions_router, "create_image_submission", broken_analysis)
    before = set(Path(settings.UPLOAD_DIR).iterdir())
    token = _register("image.orphan@example.com")
    failing_client = TestClient(app, raise_server_exceptions=False)
    response = failing_client.post(
        "/submissions/image",
        headers=_auth_headers(token),
        files={"file": ("x.png", _png_bytes(), "image/png")},
    )
    assert response.status_code == 500
    assert set(Path(settings.UPLOAD_DIR).iterdir()) == before


def test_admin_can_read_any_submission_and_image():
    owner = _register("owner.for.admin@example.com")
    created = client.post(
        "/submissions/image",
        headers=_auth_headers(owner),
        files={"file": ("x.png", _png_bytes(), "image/png")},
    ).json()
    admin = _make_admin("detail.admin@example.com")

    detail = client.get(f"/submissions/{created['id']}", headers=_auth_headers(admin))
    assert detail.status_code == 200
    image = client.get(f"/submissions/{created['id']}/image", headers=_auth_headers(admin))
    assert image.status_code == 200
    assert image.headers["content-type"] == "image/png"

    stranger = _register("stranger.image@example.com")
    assert client.get(f"/submissions/{created['id']}/image", headers=_auth_headers(stranger)).status_code == 404
