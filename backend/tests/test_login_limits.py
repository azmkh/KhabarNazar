"""Failed-login limits (app/utils/login_limiter.py) and removed debug endpoints."""
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.utils import login_limiter as limiter_module

client = TestClient(app)
PASSWORD = "Password123!"


@pytest.fixture
def account():
    email = "limit.user@example.com"
    response = client.post("/auth/register", json={"name": "Limit User", "email": email, "password": PASSWORD})
    assert response.status_code in (201, 400)  # 400 = already created by an earlier test in this run
    return email


def _login(email: str, password: str):
    return client.post("/auth/login", json={"email": email, "password": password})


def test_account_locks_after_repeated_failures(account):
    limit = settings.LOGIN_MAX_FAILURES_PER_ACCOUNT
    for _ in range(limit):
        assert _login(account, "wrong-password").status_code == 401

    blocked = _login(account, "wrong-password")
    assert blocked.status_code == 429
    assert "too many failed sign-in attempts" in blocked.json()["detail"].lower()
    assert int(blocked.headers["Retry-After"]) > 0

    # Even the right password is refused during the lockout.
    assert _login(account, PASSWORD).status_code == 429


def test_lockout_is_per_account(account):
    for _ in range(settings.LOGIN_MAX_FAILURES_PER_ACCOUNT):
        _login(account, "wrong-password")
    other = "limit.other@example.com"
    client.post("/auth/register", json={"name": "Other User", "email": other, "password": PASSWORD})
    assert _login(other, PASSWORD).status_code == 200


def test_successful_login_resets_the_count(account):
    for _ in range(settings.LOGIN_MAX_FAILURES_PER_ACCOUNT - 1):
        _login(account, "wrong-password")
    assert _login(account, PASSWORD).status_code == 200
    # The count started again, so another failure does not lock the account.
    assert _login(account, "wrong-password").status_code == 401
    assert _login(account, PASSWORD).status_code == 200


def test_client_limit_across_many_emails(monkeypatch):
    monkeypatch.setattr(settings, "LOGIN_MAX_FAILURES_PER_CLIENT", 3)
    for i in range(3):
        assert _login(f"nobody{i}@example.com", "whatever").status_code == 401
    assert _login("nobody-else@example.com", "whatever").status_code == 429


def test_lockout_expires(account, monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(limiter_module.time, "monotonic", lambda: now[0])
    for _ in range(settings.LOGIN_MAX_FAILURES_PER_ACCOUNT):
        _login(account, "wrong-password")
    assert _login(account, PASSWORD).status_code == 429

    now[0] += settings.LOGIN_LOCKOUT_MINUTES * 60 + 1
    assert _login(account, PASSWORD).status_code == 200


def test_debug_admin_endpoint_is_gone():
    assert client.get("/users/admin-test").status_code == 404
    assert client.get("/api/v1/users/admin-test").status_code == 404
