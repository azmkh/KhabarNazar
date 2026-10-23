import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from download_models import download_file


class FakeResponse:
    def __init__(self, body: bytes, status: int, headers: dict[str, str]):
        self.body = body
        self.status = status
        self.headers = headers

    def __enter__(self): return self
    def __exit__(self, *args): return False
    def read(self, size: int):
        body, self.body = self.body[:size], self.body[size:]
        return body


def test_download_resumes_only_matching_http_range(tmp_path, monkeypatch):
    partial = tmp_path / "model.safetensors.part"
    partial.write_bytes(b"prefix-")
    body = b"remaining-bytes"
    seen = {}

    def open_request(request, timeout):
        seen["range"] = request.get_header("Range")
        return FakeResponse(body, 206, {
            "Content-Range": f"bytes 7-{7 + len(body) - 1}/{7 + len(body)}",
            "Content-Length": str(len(body)),
        })

    monkeypatch.setattr("urllib.request.urlopen", open_request)
    download_file("https://example.invalid/model", partial)
    assert seen["range"] == "bytes=7-"
    assert partial.read_bytes() == b"prefix-" + body


def test_download_restarts_when_server_ignores_range(tmp_path, monkeypatch):
    partial = tmp_path / "model.part"
    partial.write_bytes(b"old partial")
    body = b"complete model"
    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: FakeResponse(
        body, 200, {"Content-Length": str(len(body))}
    ))
    download_file("https://example.invalid/model", partial)
    assert partial.read_bytes() == body


def test_download_rejects_incomplete_content_length(tmp_path, monkeypatch):
    partial = tmp_path / "model.part"
    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: FakeResponse(
        b"short", 200, {"Content-Length": "100"}
    ))
    with pytest.raises(IOError, match="Incomplete download"):
        download_file("https://example.invalid/model", partial)
