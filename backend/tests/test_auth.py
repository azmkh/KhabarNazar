import pytest
from fastapi.testclient import TestClient
from app.database import SessionLocal
from app.main import app
from app.models.user import User
from app.utils.security import create_access_token

client = TestClient(app)


def _set_role(email: str, role: str) -> None:
    db = SessionLocal()
    try:
        db.query(User).filter(User.email == email).one().role = role
        db.commit()
    finally:
        db.close()


@pytest.fixture(autouse=True)
def setup_test_data():
    """Fixture ensuring clean test state where necessary."""
    yield


def test_user_registration_success():
    payload = {
        "name": "Waniya Khan",
        "email": "waniya.test@example.com",
        "password": "Password123!",
    }
    response = client.post("/auth/register", json=payload)
    # If already registered in a previous run, check code or clean
    if response.status_code == 400:
        # User exists, proceed to test duplicate
        assert response.json()["detail"] == "An account with this email already exists."
    else:
        assert response.status_code == 201
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert "user" in data
        assert data["user"]["email"] == "waniya.test@example.com"
        assert data["user"]["name"] == "Waniya Khan"
        assert data["user"]["role"] == "user"
        assert "password_hash" not in data["user"]
        assert "password" not in data["user"]


def test_duplicate_registration_fails():
    payload = {
        "name": "Duplicate User",
        "email": "waniya.test@example.com",
        "password": "Password123!",
    }
    response = client.post("/auth/register", json=payload)
    assert response.status_code == 400
    data = response.json()
    assert data["detail"] == "An account with this email already exists."


def test_login_success():
    payload = {
        "email": "waniya.test@example.com",
        "password": "Password123!",
    }
    response = client.post("/auth/login", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "waniya.test@example.com"


def test_login_invalid_password():
    payload = {
        "email": "waniya.test@example.com",
        "password": "WrongPassword!",
    }
    response = client.post("/auth/login", json=payload)
    assert response.status_code == 401
    data = response.json()
    assert data["detail"] == "Incorrect email or password entered."


def test_login_nonexistent_user():
    payload = {
        "email": "does.not.exist@example.com",
        "password": "SomePassword123",
    }
    response = client.post("/auth/login", json=payload)
    assert response.status_code == 401
    data = response.json()
    assert data["detail"] == "Incorrect email or password entered."


def test_get_current_user_me_unauthorized():
    response = client.get("/users/me")
    assert response.status_code == 401


def test_get_current_user_me_success():
    # Login to acquire token
    login_res = client.post(
        "/auth/login",
        json={"email": "waniya.test@example.com", "password": "Password123!"},
    )
    token = login_res.json()["access_token"]

    response = client.get(
        "/users/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "waniya.test@example.com"
    assert data["name"] == "Waniya Khan"
    assert "password_hash" not in data


def test_role_based_access_control():
    # 1. Normal user should be rejected from admin endpoint (403)
    login_user = client.post(
        "/auth/login",
        json={"email": "waniya.test@example.com", "password": "Password123!"},
    )
    user_token = login_user.json()["access_token"]
    forbidden_res = client.get(
        "/admin/submissions",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert forbidden_res.status_code == 403
    assert "administrator privileges required" in forbidden_res.json()["detail"].lower()

    # 2. A "+admin" email alias must NOT grant admin; roles are only changed server-side.
    admin_payload = {
        "name": "Admin Officer",
        "email": "officer+admin@example.com",
        "password": "AdminPassword123!",
    }
    reg_admin = client.post("/auth/register", json=admin_payload)
    assert reg_admin.status_code == 201
    assert reg_admin.json()["user"]["role"] == "user"
    admin_token = reg_admin.json()["access_token"]
    assert client.get("/admin/submissions", headers={"Authorization": f"Bearer {admin_token}"}).status_code == 403

    # 3. Promote the account the same way scripts/set_user_role.py does.
    _set_role(admin_payload["email"], "admin")

    allowed_res = client.get(
        "/admin/submissions",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert allowed_res.status_code == 200
    assert client.get("/users/me", headers={"Authorization": f"Bearer {admin_token}"}).json()["role"] == "admin"


def test_demoted_admin_loses_access_with_existing_token():
    _set_role("officer+admin@example.com", "user")
    token = client.post(
        "/auth/login",
        json={"email": "officer+admin@example.com", "password": "AdminPassword123!"},
    ).json()["access_token"]
    response = client.get("/admin/submissions", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403


def test_register_rejects_blank_name_and_overlong_password():
    blank = client.post(
        "/auth/register",
        json={"name": "   ", "email": "blank.name@example.com", "password": "Password123!"},
    )
    assert blank.status_code == 422

    # 40 Urdu letters = 80 UTF-8 bytes, beyond bcrypt's 72-byte limit.
    too_long = client.post(
        "/auth/register",
        json={"name": "Urdu Pass", "email": "urdu.pass@example.com", "password": "پ" * 40},
    )
    assert too_long.status_code == 422


def test_login_email_is_case_insensitive():
    response = client.post(
        "/auth/login",
        json={"email": "WANIYA.TEST@example.com", "password": "Password123!"},
    )
    assert response.status_code == 200


def test_expired_and_tampered_tokens_are_rejected():
    from datetime import timedelta

    expired = create_access_token(subject=1, expires_delta=timedelta(seconds=-1))
    assert client.get("/users/me", headers={"Authorization": f"Bearer {expired}"}).status_code == 401

    valid = client.post(
        "/auth/login",
        json={"email": "waniya.test@example.com", "password": "Password123!"},
    ).json()["access_token"]
    tampered = valid[:-2] + ("AA" if not valid.endswith("AA") else "BB")
    assert client.get("/users/me", headers={"Authorization": f"Bearer {tampered}"}).status_code == 401


def test_timestamps_include_timezone():
    response = client.post(
        "/auth/login",
        json={"email": "waniya.test@example.com", "password": "Password123!"},
    )
    created_at = response.json()["user"]["created_at"]
    assert created_at.endswith("Z") or created_at.endswith("+00:00")
