"""Production settings: check rate limits, proxy client address, DB pool options, Volume sync, /health models."""
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from starlette.requests import Request

from app.config import settings
from app.database import engine_options
from app.main import app
from app.utils import storage
from app.utils.login_limiter import client_address
from app.utils.rate_limit import SlidingWindowLimiter

client = TestClient(app)
TEXT = "یہ ایک جانچ کے لیے لکھی گئی خبر ہے جس میں کافی الفاظ موجود ہیں"


def _token(email: str) -> str:
    response = client.post("/auth/register", json={"name": "Rate User", "email": email, "password": "Password123!"})
    assert response.status_code == 201
    login = client.post("/auth/login", json={"email": email, "password": "Password123!"})
    return login.json()["access_token"]


def test_check_endpoints_are_rate_limited_per_user():
    first = {"Authorization": f"Bearer {_token('rate.one@example.com')}"}
    second = {"Authorization": f"Bearer {_token('rate.two@example.com')}"}
    with patch.object(settings, "CHECK_RATE_LIMIT_PER_MINUTE", 2):
        for _ in range(2):
            assert client.post("/submissions/text", json={"text": TEXT}, headers=first).status_code == 201
        blocked = client.post("/submissions/text", json={"text": TEXT}, headers=first)
        assert blocked.status_code == 429
        assert int(blocked.headers["Retry-After"]) > 0
        # Images count towards the same limit; another user is unaffected.
        image = client.post("/submissions/image", files={"file": ("x.png", b"not checked", "image/png")}, headers=first)
        assert image.status_code == 429
        assert client.post("/submissions/text", json={"text": TEXT}, headers=second).status_code == 201
        # Reading history is not limited.
        assert client.get("/submissions", headers=first).status_code == 200


def test_rate_limit_zero_disables_it():
    headers = {"Authorization": f"Bearer {_token('rate.off@example.com')}"}
    with patch.object(settings, "CHECK_RATE_LIMIT_PER_MINUTE", 0), patch.object(settings, "CHECK_RATE_LIMIT_PER_HOUR", 0):
        for _ in range(3):
            assert client.post("/submissions/text", json={"text": TEXT}, headers=headers).status_code == 201


def test_sliding_window_reports_wait_and_does_not_count_refused_requests():
    limiter = SlidingWindowLimiter()
    assert limiter.hit("k", [(1, 60.0)]) is None
    assert 0 < limiter.hit("k", [(1, 60.0)]) <= 60
    assert len(limiter._hits["k"]) == 1


def _request(forwarded: str | None) -> Request:
    headers = [(b"x-forwarded-for", forwarded.encode())] if forwarded else []
    return Request({"type": "http", "headers": headers, "client": ("10.0.0.1", 1234)})


def test_client_address_uses_forwarded_header_only_behind_a_trusted_proxy():
    assert client_address(_request("203.0.113.9, 10.0.0.2")) == "10.0.0.1"
    with patch.object(settings, "TRUST_PROXY_HEADERS", True):
        assert client_address(_request("203.0.113.9, 10.0.0.2")) == "203.0.113.9"
        assert client_address(_request(None)) == "10.0.0.1"


def test_neon_pooled_url_gets_tls_small_pool_and_no_prepared_statements():
    options = engine_options("postgresql+psycopg://u:p@ep-x-pooler.us-east-1.aws.neon.tech/db")
    assert options["connect_args"] == {"sslmode": "require", "prepare_threshold": None}
    assert options["pool_pre_ping"] is True
    assert options["pool_size"] == settings.DB_POOL_SIZE
    # An explicit sslmode in the URL is kept; a local server gets no TLS or pooler options.
    explicit = engine_options("postgresql+psycopg://u:p@ep-x.us-east-1.aws.neon.tech/db?sslmode=verify-full")
    assert "sslmode" not in explicit["connect_args"]
    assert engine_options("postgresql+psycopg://u:p@localhost/db")["connect_args"] == {}
    assert engine_options("sqlite:///x.db")["connect_args"] == {"check_same_thread": False}


class FakeVolume:
    def __init__(self, on_reload=None):
        self.commits = 0
        self.reloads = 0
        self.on_reload = on_reload

    def commit(self):
        self.commits += 1

    def reload(self):
        self.reloads += 1
        if self.on_reload:
            self.on_reload()


def test_storage_hooks_are_no_ops_without_a_volume(tmp_path: Path):
    storage.use_volume(None)
    storage.persist()
    assert storage.ensure_visible(tmp_path / "missing.png") is False


def test_volume_is_committed_after_upload_and_reloaded_for_missing_files(tmp_path: Path):
    target = tmp_path / "written_elsewhere.png"
    volume = FakeVolume(on_reload=lambda: target.write_bytes(b"x"))
    storage.use_volume(volume)
    try:
        storage.persist()
        assert volume.commits == 1
        assert storage.ensure_visible(target) is True
        assert volume.reloads == 1
        assert storage.ensure_visible(target) is True  # present now: no second reload
        assert volume.reloads == 1
    finally:
        storage.use_volume(None)


def test_image_upload_commits_the_volume():
    headers = {"Authorization": f"Bearer {_token('volume.user@example.com')}"}
    import io

    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (8, 8), (10, 20, 30)).save(buffer, format="PNG")
    volume = FakeVolume()
    storage.use_volume(volume)
    try:
        response = client.post(
            "/submissions/image", files={"file": ("a.png", buffer.getvalue(), "image/png")}, headers=headers
        )
    finally:
        storage.use_volume(None)
    assert response.status_code == 201
    assert volume.commits == 1


def test_health_reports_model_status_without_loading_models():
    data = client.get("/health").json()
    models = data["models"]
    assert set(models) == {"ready", "warmup", "models"}
    assert models["warmup"] == "not_started"  # PRELOAD_MODELS is off in tests
    # The test settings point every model at a missing folder.
    assert models["models"]["urdu_text"] == "not_configured"
    assert models["models"]["image_detector"] == "not_configured"
