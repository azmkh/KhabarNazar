"""
Isolate backend tests on a throwaway SQLite database and upload folder.

This module must set environment variables before `app.main` is imported
by any test file. The schema is created by running the real Alembic
migrations, so a broken migration fails the test suite.
"""
import os
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
BACKEND_DIR = TEST_DIR.parent
TEST_DB = TEST_DIR / "_test.db"
TEST_UPLOADS = TEST_DIR / "_uploads"

if TEST_DB.exists():
    TEST_DB.unlink()

TEST_UPLOADS.mkdir(parents=True, exist_ok=True)

os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB.as_posix()}"
os.environ["JWT_SECRET"] = "test-jwt-secret-not-for-production-0123456789"
os.environ["UPLOAD_DIR"] = str(TEST_UPLOADS)
os.environ["ENVIRONMENT"] = "test"
# Never pick up a locally trained model during tests unless a test opts in.
os.environ["KHABARNAZAR_TEXT_MODEL_PATH"] = str(TEST_DIR / "_no_model.joblib")
os.environ["KHABARNAZAR_URDU_XLMR_DIR"] = str(TEST_DIR / "_no_urdu_xlmr")
os.environ["KHABARNAZAR_ROMAN_XLMR_DIR"] = str(TEST_DIR / "_no_roman_xlmr")

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402

_alembic_config = Config(str(BACKEND_DIR / "alembic.ini"))
_alembic_config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
command.upgrade(_alembic_config, "head")


# SQLite ignores VARCHAR lengths but PostgreSQL rejects values that are too long.
# Enforce them in tests so such bugs are caught before reaching PostgreSQL.
from sqlalchemy import String, event  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402


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
