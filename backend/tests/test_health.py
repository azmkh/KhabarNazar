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


def test_health_reports_migrations_up_to_date():
    data = client.get("/health").json()
    assert data["migrations"]["status"] == "up_to_date"
    assert data["migrations"]["current"] == data["migrations"]["head"]


def _behind():
    return {"status": "behind", "current": "d2e7b4c19a35", "head": "e5b1c7a3d920"}


def test_health_is_degraded_when_the_database_is_behind_the_code():
    with patch("app.main.check_migrations", _behind):
        response = client.get("/health")
    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "degraded" and data["migrations"]["status"] == "behind"
    assert "alembic upgrade head" in data["message"]


def test_database_errors_explain_a_missing_migration():
    from sqlalchemy.exc import OperationalError

    register = client.post("/auth/register", json={"name": "Migration Tester", "email": "behind@example.com", "password": "Password123!"})
    headers = {"Authorization": f"Bearer {register.json()['access_token']}"}

    def broken(*args, **kwargs):
        raise OperationalError("SELECT ...", {}, Exception("no such column: image_submissions.ocr_status"))

    with patch("app.routers.submissions.get_user_submissions", broken):
        with patch("app.main.check_migrations", _behind):
            behind = client.get("/submissions", headers=headers)
        current = client.get("/submissions", headers=headers)
    assert behind.status_code == 503 and "alembic upgrade head" in behind.json()["detail"]
    # A database error with an up-to-date schema stays a plain 500 that leaks nothing.
    assert current.status_code == 500 and current.json() == {"detail": "Internal server error"}


def test_migration_head_is_the_single_newest_script():
    from alembic.script import ScriptDirectory

    from app.database import ALEMBIC_DIR, migration_head

    heads = ScriptDirectory(str(ALEMBIC_DIR)).get_heads()
    assert len(heads) == 1 and migration_head() == heads[0]
