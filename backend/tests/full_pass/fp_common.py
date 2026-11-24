"""Shared settings for the full test pass (throwaway servers only)."""
from __future__ import annotations

import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
BACKEND = HERE.parents[1]
PY = BACKEND / ".venv" / "Scripts" / "python.exe"

# JWT secret of the THROWAWAY test servers only (never the real backend/.env secret). The runner
# knows it so it can mint expired and tampered tokens for TC-LOG-09/10/12.
TEST_JWT_SECRET = "full-pass-throwaway-secret-not-used-anywhere-else-0123456789"
CORS_TEST_REGEX = r"^https://khabarnazar(--[a-z0-9-]+)?\.expo\.app$"


def test_postgres_url() -> str:
    """TEST_DATABASE_URL from backend/.env (the isolated *_test database). Never printed."""
    from dotenv import dotenv_values

    url = os.environ.get("TEST_DATABASE_URL") or dotenv_values(BACKEND / ".env").get("TEST_DATABASE_URL")
    if not url or not url.split("?")[0].rsplit("/", 1)[-1].endswith("_test"):
        raise SystemExit("TEST_DATABASE_URL must point at a database whose name ends in _test")
    return url


def resolve_db(spec: str) -> str:
    """'sqlite:<path>' or 'postgres' -> a SQLAlchemy URL."""
    if spec == "postgres":
        return test_postgres_url()
    if spec.startswith("sqlite:"):
        return "sqlite:///" + Path(spec[len("sqlite:"):]).resolve().as_posix()
    raise SystemExit(f"unknown --db {spec!r}")
