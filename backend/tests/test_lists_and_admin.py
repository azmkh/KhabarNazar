"""Task 5: paging totals, admin's own disputes, admin submission list and stats."""
import itertools

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models.user import User

client = TestClient(app)
_ids = itertools.count()


def _user(role: str = "user") -> dict:
    email = f"lists.{role}.{next(_ids)}@example.com"
    response = client.post("/auth/register", json={"name": "List Tester", "email": email, "password": "Password123!"})
    assert response.status_code in (201, 400), response.text
    if response.status_code == 400:  # already exists from an earlier run of this module
        response = client.post("/auth/login", json={"email": email, "password": "Password123!"})
    if role != "user":
        db = SessionLocal()
        try:
            db.query(User).filter(User.email == email).one().role = role
            db.commit()
        finally:
            db.close()
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _submit(headers: dict, text: str) -> int:
    response = client.post("/submissions/text", json={"text": text}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_history_pages_have_no_gaps_or_overlap_and_report_total():
    user = _user()
    created = [_submit(user, f"Paging check number {i} for the history list") for i in range(7)]
    _submit(_user(), "Someone else's check, not counted for this user")

    pages = []
    for skip in (0, 3, 6):
        response = client.get(f"/api/v1/submissions?skip={skip}&limit=3", headers=user)
        assert response.status_code == 200
        assert response.headers["X-Total-Count"] == "7"
        pages.append([item["id"] for item in response.json()])

    assert [len(page) for page in pages] == [3, 3, 1]
    flat = [i for page in pages for i in page]
    assert len(set(flat)) == 7
    assert flat == sorted(created, reverse=True)  # newest first, all of them exactly once


def test_admin_can_list_only_their_own_disputes():
    admin = _user("admin")
    user = _user()
    admin_submission = _submit(admin, "The admin's own check that the admin disputes")
    user_submission = _submit(user, "A normal user's check that the user disputes")
    reason = "This verdict looks wrong to me, please review."
    assert client.post("/disputes", json={"submission_id": admin_submission, "justification": reason}, headers=admin).status_code == 201
    assert client.post("/disputes", json={"submission_id": user_submission, "justification": reason}, headers=user).status_code == 201

    everyone = client.get("/disputes?limit=100", headers=admin)
    mine = client.get("/disputes?mine=true", headers=admin)
    assert user_submission in {d["submission_id"] for d in everyone.json()}
    assert [d["submission_id"] for d in mine.json()] == [admin_submission]
    assert mine.headers["X-Total-Count"] == "1"
    assert int(everyone.headers["X-Total-Count"]) >= 2

    # For a normal user, mine=true changes nothing: they only ever see their own.
    assert [d["submission_id"] for d in client.get("/disputes?mine=true", headers=user).json()] == [user_submission]
    assert client.get("/disputes", headers=user).headers["X-Total-Count"] == "1"


def test_admin_submission_list_includes_submitter_and_latest_dispute():
    admin = _user("admin")
    user = _user()
    disputed = _submit(user, "A check that gets disputed twice over time")
    plain = _submit(user, "A check that is never disputed")
    first = client.post("/disputes", json={"submission_id": disputed, "justification": "First objection to this result."}, headers=user).json()
    review = {"admin_decision": "uphold_ai", "admin_comment": "Reviewed and upheld."}
    assert client.patch(f"/disputes/{first['id']}", json=review, headers=admin).status_code == 200
    second = client.post("/disputes", json={"submission_id": disputed, "justification": "Second objection with new evidence."}, headers=user).json()

    response = client.get("/admin/submissions?limit=100", headers=admin)
    assert response.status_code == 200
    rows = {row["id"]: row for row in response.json()}
    assert rows[disputed]["dispute_count"] == 2
    assert rows[disputed]["latest_dispute_id"] == second["id"]
    assert rows[disputed]["latest_dispute_status"] == "pending"
    assert rows[disputed]["user_email"].startswith("lists.user.")
    assert rows[plain]["dispute_count"] == 0 and rows[plain]["latest_dispute_id"] is None
    assert "text_submission" in rows[plain]  # still the full submission shape

    stats = client.get("/admin/stats", headers=admin).json()
    assert response.headers["X-Total-Count"] == str(stats["submissions"])


def test_admin_stats_count_the_whole_database():
    admin = _user("admin")
    before = client.get("/admin/stats", headers=admin).json()

    user = _user()
    submission = _submit(user, "A check counted in the admin statistics")
    dispute = client.post("/disputes", json={"submission_id": submission, "justification": "Please look at this verdict again."}, headers=user).json()
    middle = client.get("/admin/stats", headers=admin).json()
    assert middle["users"] == before["users"] + 1  # only the new user; the admin existed before `before`
    assert middle["submissions"] == before["submissions"] + 1
    assert middle["submissions_by_type"].get("text", 0) == before["submissions_by_type"].get("text", 0) + 1
    assert middle["submissions_by_label"].get("Uncertain", 0) == before["submissions_by_label"].get("Uncertain", 0) + 1
    assert middle["disputes"]["pending"] == before["disputes"]["pending"] + 1

    override = {"admin_decision": "override", "admin_comment": "Checked against the source.", "override_label": "Real"}
    assert client.patch(f"/disputes/{dispute['id']}", json=override, headers=admin).status_code == 200
    after = client.get("/admin/stats", headers=admin).json()
    assert after["disputes"]["pending"] == before["disputes"]["pending"]
    assert after["disputes"]["reviewed"] == before["disputes"]["reviewed"] + 1
    assert after["admin_overrides"] == before["admin_overrides"] + 1
    assert after["submissions_by_label"].get("Real", 0) == before["submissions_by_label"].get("Real", 0) + 1


def test_stats_and_admin_list_require_admin():
    user = _user()
    assert client.get("/admin/stats", headers=user).status_code == 403
    assert client.get("/admin/stats").status_code == 401


def test_browsers_may_read_the_total_header():
    user = _user()
    response = client.get("/submissions", headers={**user, "Origin": "http://localhost:8081"})
    assert "x-total-count" in response.headers.get("access-control-expose-headers", "").lower()
