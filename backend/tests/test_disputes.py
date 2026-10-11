"""Stage 8: disputes and administrator review."""
from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models.user import User

client = TestClient(app)


def _headers(email: str, role: str = "user") -> dict:
    response = client.post("/auth/register", json={"name": "Dispute Tester", "email": email, "password": "Password123!"})
    assert response.status_code == 201, response.text
    if role != "user":
        db = SessionLocal()
        try:
            db.query(User).filter(User.email == email).one().role = role
            db.commit()
        finally:
            db.close()
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _submission(headers: dict) -> int:
    response = client.post("/submissions/text", json={"text": "Yeh khabar viral ho rahi hai."}, headers=headers)
    assert response.status_code == 201
    return response.json()["id"]


JUSTIFICATION = "The official press release contradicts this result."


def test_dispute_lifecycle_with_admin_override():
    user = _headers("dispute.owner@example.com")
    admin = _headers("dispute.admin@example.com", role="admin")
    submission_id = _submission(user)

    created = client.post(
        "/disputes",
        json={"submission_id": submission_id, "justification": JUSTIFICATION, "evidence_link": "https://example.com/pr"},
        headers=user,
    )
    assert created.status_code == 201, created.text
    dispute = created.json()
    assert dispute["status"] == "pending"

    duplicate = client.post("/disputes", json={"submission_id": submission_id, "justification": JUSTIFICATION}, headers=user)
    assert duplicate.status_code == 409

    review = {"admin_decision": "override", "admin_comment": "Verified against the official source.", "override_label": "Real"}
    assert client.patch(f"/disputes/{dispute['id']}", json=review, headers=user).status_code == 403

    reviewed = client.patch(f"/disputes/{dispute['id']}", json=review, headers=admin)
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["status"] == "reviewed"
    assert reviewed.json()["reviewed_at"] is not None

    submission = client.get(f"/submissions/{submission_id}", headers=user).json()
    assert submission["final_label"] == "Real"
    assert submission["final_label_source"] == "Admin"
    assert submission["admin_comment"] == "Verified against the official source."

    again = client.patch(f"/disputes/{dispute['id']}", json=review, headers=admin)
    assert again.status_code == 409


def test_uphold_keeps_ai_label():
    user = _headers("dispute.uphold@example.com")
    admin = _headers("dispute.uphold.admin@example.com", role="admin")
    submission_id = _submission(user)
    dispute = client.post("/disputes", json={"submission_id": submission_id, "justification": JUSTIFICATION}, headers=user).json()

    response = client.patch(
        f"/disputes/{dispute['id']}",
        json={"admin_decision": "uphold_ai", "admin_comment": "The AI result stands."},
        headers=admin,
    )
    assert response.status_code == 200
    submission = client.get(f"/submissions/{submission_id}", headers=user).json()
    assert submission["final_label_source"] == "AI"


def test_dispute_validation_and_ownership():
    owner = _headers("dispute.validate@example.com")
    stranger = _headers("dispute.stranger@example.com")
    admin = _headers("dispute.validate.admin@example.com", role="admin")
    submission_id = _submission(owner)

    assert client.post("/disputes", json={"submission_id": submission_id, "justification": JUSTIFICATION}, headers=stranger).status_code == 404
    assert client.post("/disputes", json={"submission_id": submission_id, "justification": "short"}, headers=owner).status_code == 422
    assert client.post(
        "/disputes",
        json={"submission_id": submission_id, "justification": JUSTIFICATION, "evidence_link": "javascript:alert(1)"},
        headers=owner,
    ).status_code == 422

    dispute = client.post("/disputes", json={"submission_id": submission_id, "justification": JUSTIFICATION}, headers=owner).json()
    assert client.get(f"/disputes/{dispute['id']}", headers=stranger).status_code == 404
    assert all(item["user_id"] != dispute["user_id"] for item in client.get("/disputes", headers=stranger).json())

    # Override without a label is rejected.
    assert client.patch(
        f"/disputes/{dispute['id']}",
        json={"admin_decision": "override", "admin_comment": "Missing label"},
        headers=admin,
    ).status_code == 422

    pending = client.get("/disputes?status=pending", headers=admin).json()
    assert dispute["id"] in {item["id"] for item in pending}


def test_admin_submission_list_requires_admin():
    user = _headers("admin.list.user@example.com")
    admin = _headers("admin.list.admin@example.com", role="admin")
    _submission(user)
    assert client.get("/admin/submissions", headers=user).status_code == 403
    response = client.get("/admin/submissions", headers=admin)
    assert response.status_code == 200
    assert len(response.json()) >= 1
