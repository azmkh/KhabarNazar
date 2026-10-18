"""
Isolate backend tests on a throwaway database and upload folder.

By default the tests use a temporary SQLite file. With `pytest --postgres`
they run against the PostgreSQL database in TEST_DATABASE_URL (set in
backend/.env by scripts/setup_postgres.py). That database is wiped at the
start of every run, so its name must end with "_test".

Either way the schema is created by running the real Alembic migrations, so a
broken migration fails the test suite. Environment variables are set in
pytest_configure, before any test module imports `app.main`.
"""
import os
from pathlib import Path

import pytest
from sqlalchemy import String, event
from sqlalchemy.orm import Session

TEST_DIR = Path(__file__).resolve().parent
BACKEND_DIR = TEST_DIR.parent
TEST_DB = TEST_DIR / "_test.db"
TEST_UPLOADS = TEST_DIR / "_uploads"


def pytest_addoption(parser):
    parser.addoption(
        "--postgres",
        action="store_true",
        help="run against the PostgreSQL database in TEST_DATABASE_URL (it is wiped first)",
    )


def _postgres_test_url() -> str:
    from dotenv import dotenv_values
    from sqlalchemy.engine import make_url

    url = os.environ.get("TEST_DATABASE_URL") or dotenv_values(BACKEND_DIR / ".env").get("TEST_DATABASE_URL")
    if not url:
        raise pytest.UsageError("--postgres needs TEST_DATABASE_URL (run scripts/setup_postgres.py first)")
    parsed = make_url(url)
    if not parsed.drivername.startswith("postgresql") or not (parsed.database or "").endswith("_test"):
        raise pytest.UsageError("TEST_DATABASE_URL must be a PostgreSQL database whose name ends with '_test'")
    return url


def _wipe_postgres(url: str) -> None:
    from sqlalchemy import create_engine, text

    engine = create_engine(url)
    with engine.begin() as connection:
        # Removes every table/type this role created in the test database.
        connection.execute(text("DROP OWNED BY CURRENT_USER"))
        connection.execute(text("CREATE SCHEMA IF NOT EXISTS public"))
    engine.dispose()


def pytest_configure(config):
    if config.getoption("--postgres"):
        database_url = _postgres_test_url()
        _wipe_postgres(database_url)
    else:
        if TEST_DB.exists():
            TEST_DB.unlink()
        database_url = f"sqlite:///{TEST_DB.as_posix()}"

    TEST_UPLOADS.mkdir(parents=True, exist_ok=True)
    os.environ["DATABASE_URL"] = database_url
    os.environ["JWT_SECRET"] = "test-jwt-secret-not-for-production-0123456789"
    os.environ["UPLOAD_DIR"] = str(TEST_UPLOADS)
    os.environ["ENVIRONMENT"] = "test"
    # Never pick up a locally trained model during tests unless a test opts in.
    os.environ["KHABARNAZAR_TEXT_MODEL_PATH"] = str(TEST_DIR / "_no_model.joblib")

    from alembic import command
    from alembic.config import Config

    alembic_config = Config(str(BACKEND_DIR / "alembic.ini"))
    alembic_config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    command.upgrade(alembic_config, "head")


def pytest_report_header(config):
    return "database: PostgreSQL (TEST_DATABASE_URL)" if config.getoption("--postgres") else "database: SQLite (temporary file)"


# SQLite ignores VARCHAR lengths but PostgreSQL rejects values that are too long.
# Enforce them in tests so such bugs are caught even in the SQLite run.
@event.listens_for(Session, "before_flush")
def _enforce_string_lengths(session, flush_context, instances):
    for obj in list(session.new) + list(session.dirty):
        for column in obj.__table__.columns:
            limit = getattr(column.type, "length", None)
            value = getattr(obj, column.key, None)
            if isinstance(column.type, String) and limit and isinstance(value, str) and len(value) > limit:
                raise AssertionError(
                    f"{obj.__tablename__}.{column.key} is limited to {limit} characters, got {len(value)}: {value!r}"
                )


@pytest.fixture(autouse=True)
def _reset_login_limiter():
    """Every test request comes from the same fake client, so failed logins in
    one test must not lock out the next."""
    from app.utils.login_limiter import login_limiter

    login_limiter.clear()
    yield
    login_limiter.clear()
