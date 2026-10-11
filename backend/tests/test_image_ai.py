"""Stage 6/7: OCR fallback and heatmap rendering/serving."""
import io

import numpy as np
from fastapi.testclient import TestClient
from PIL import Image

from app.main import app

client = TestClient(app)


def _png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (32, 32), (200, 200, 200)).save(buf, format="PNG")
    return buf.getvalue()


def _headers(email: str) -> dict:
    response = client.post("/auth/register", json={"name": "Image Tester", "email": email, "password": "Password123!"})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_ocr_reports_unavailable_instead_of_inventing_text(tmp_path, monkeypatch):
    import app.ai.image.ocr as ocr

    def missing_reader(directory):
        raise ImportError("easyocr not installed")

    monkeypatch.setattr(ocr, "_get_ocr_reader", missing_reader)
    image = tmp_path / "x.png"
    image.write_bytes(_png())
    result = ocr.run_ocr(str(image))
    assert result["text"] is None
    assert result["status"] == "dependency_missing"


def test_heatmap_is_rendered_and_served_only_to_owner(monkeypatch):
    import app.services.submission_service as service

    # Stand-in for a future visual model that returns an attribution map.
    monkeypatch.setattr(service, "analyze_image", lambda path: {
        "image_score": 0.6,
        "manipulation_prediction": "Manipulated",
        "attribution_map": np.linspace(0, 1, 16).reshape(4, 4),
        "is_stub": False,
    })
    owner = _headers("heatmap.owner@example.com")
    data = client.post("/submissions/image", headers=owner, files={"file": ("x.png", _png(), "image/png")}).json()
    assert data["explainability"]["heatmap_path"] == f"explanations/{data['id']}_heatmap.png"
    assert data["image_submission"]["image_score"] == 0.6

    heatmap = client.get(f"/submissions/{data['id']}/heatmap", headers=owner)
    assert heatmap.status_code == 200
    assert heatmap.headers["content-type"] == "image/png"

    other = _headers("heatmap.other@example.com")
    assert client.get(f"/submissions/{data['id']}/heatmap", headers=other).status_code == 404
