from unittest.mock import patch

from fastapi.testclient import TestClient
from app.config import BASE_DIR, Settings
from app.main import app

client = TestClient(app)


def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert data["project"] == "KhabarNazar Backend"
    assert "docs_url" in data
    assert "health_url" in data


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"]["status"] == "connected"
    assert "timestamp" in data


def test_health_does_not_leak_database_errors():
    class BrokenEngine:
        class dialect:
            name = "postgresql"

        def connect(self):
            raise RuntimeError("connection to server at secret-host failed for user secret-user")

    with patch("app.database.engine", BrokenEngine()):
        response = client.get("/health")
    assert response.status_code == 503
    assert "secret" not in response.text
    assert response.json()["database"]["status"] == "disconnected"


def test_relative_paths_resolve_from_backend_folder():
    settings = Settings(
        DATABASE_URL="sqlite:///./dev.db",
        JWT_SECRET="x" * 40,
        UPLOAD_DIR="uploads",
    )
    assert settings.DATABASE_URL == f"sqlite:///{(BASE_DIR / 'dev.db').resolve().as_posix()}"
    assert settings.UPLOAD_DIR == str((BASE_DIR / "uploads").resolve())


def test_short_jwt_secret_is_rejected():
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Settings(DATABASE_URL="sqlite://", JWT_SECRET="too-short")
