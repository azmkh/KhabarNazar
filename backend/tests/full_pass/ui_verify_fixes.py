"""Browser re-check of the two screen fixes: DEF-02 (overridden result) and DEF-03 (admin filters).

    python tests/full_pass/ui_verify_fixes.py --db sqlite:RUN/test.db --run-dir RUN   (from PowerShell)
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fp_common import BACKEND, PY, TEST_JWT_SECRET, resolve_db  # noqa: E402
from ui_pass import PASSWORD, Browser  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--db", required=True)
ap.add_argument("--run-dir", required=True)
ap.add_argument("--web", default="http://localhost:8082")
ap.add_argument("--api", default="http://127.0.0.1:8001")
args = ap.parse_args()
api = httpx.Client(base_url=args.api + "/api/v1", timeout=240)
tag = datetime.now().strftime("%H%M%S")
results = []


def account(key, admin=False):
    email = f"fix.{key}.{tag}@example.com"
    token = api.post("/auth/register", json={"name": f"Fix {key}", "email": email, "password": PASSWORD}).json()["access_token"]
    if admin:
        env = {k: v for k, v in os.environ.items() if not k.startswith("KHABARNAZAR_")}
        env.update({"DATABASE_URL": resolve_db(args.db), "JWT_SECRET": TEST_JWT_SECRET, "PYTHONUTF8": "1"})
        subprocess.run([str(PY), "scripts/set_user_role.py", email, "admin"], cwd=BACKEND, env=env, check=True, capture_output=True)
        token = api.post("/auth/login", json={"email": email, "password": PASSWORD}).json()["access_token"]
    return email, {"Authorization": f"Bearer {token}"}


def rec(id_, title, expected, actual, evidence, ok):
    results.append({"id": id_, "title": title, "input": "-", "expected": expected, "actual": actual, "evidence": evidence,
                    "result": "Pass" if ok else "Fail", "how": "Real (browser)", "group": "UI", "db": "verify",
                    "time": datetime.now().isoformat(timespec="seconds")})
    print(f"[{'Pass' if ok else 'Fail':4}] {id_} {actual}", flush=True)


user, uh = account("user")
admin, ah = account("admin", admin=True)
# The same Urdu claim the pass used for TC-UI-17 (the AI rated it Likely misleading, 99.9 %).
sub = api.post("/submissions/text", headers=uh, json={"text": "حکومت نے اعلان کیا ہے کہ ملک بھر میں سات دن کے لیے انٹرنیٹ سروس بند کر دی جائے گی۔"}).json()
did = api.post("/disputes", headers=uh, json={"submission_id": sub["id"], "justification": "The ministry denied this."}).json()["id"]
api.patch(f"/disputes/{did}", headers=ah, json={"admin_decision": "override", "admin_comment": "Checked with the ministry.", "override_label": "Real"})
api.post("/submissions/text", headers=uh, json={"text": "Hukoomat ne aaj naya pul khola hai aur kaam mukammal ho gaya"})

b = Browser(port=9335)
try:
    def login(email):
        b.go(args.web + "/login", 8)
        b.js("localStorage.clear()")
        b.go(args.web + "/login", 8)
        if not b.wait_text("Welcome back", 120):
            raise RuntimeError("sign-in page did not load")
        b.type("you@example.com", email)
        b.type("Your password", PASSWORD)
        b.click("Sign in", wait=4)
        if not b.wait_any(["Analyze", "Signed in as administrator"], 60):
            b.shot("FIX-debug_signin"); raise RuntimeError(f"sign-in did not complete (at {b.path()}): {b.text()[:300]!r}")

    def chip(label):
        """Click the filter chip (a role=button element), not a verdict badge in the list."""
        pos = b.js(f"""(() => {{ const e=[...document.querySelectorAll('[role=button]')].find(x => x.innerText.trim() === {json.dumps(label)});
            if (!e) return null; const r=e.getBoundingClientRect(); return [r.x+r.width/2, r.y+r.height/2]; }})()""")
        if not pos:
            raise RuntimeError(f"no chip {label!r}")
        for kind in ("mousePressed", "mouseReleased"):
            b.send("Input.dispatchMouseEvent", type=kind, x=pos[0], y=pos[1], button="left", clickCount=1)
        b.pump(4)

    login(user)
    b.go(args.web + f"/result/{sub['id']}", 10)
    b.wait_text("Final verdict", 60)
    t = b.text()
    ev = b.shot("FIX-DEF-02_overridden_result")
    hero = t[: t.find("User claim")] if "User claim" in t else t[:400]
    ok = ("Final verdict (set by an administrator)" in t and "original estimate was likely misleading" in t
          and "Score\n" not in hero and "Likely credible" in t)
    rec("TC-UI-19", "Overridden result: no AI score/risk shown as the admin verdict's numbers (DEF-02)",
        "admin label leads; the AI's numbers only as 'the AI's original estimate'", " ".join(hero.split())[:260], ev, ok)

    login(admin)
    b.go(args.web + "/admin/submissions", 10)
    b.wait_text("submissions from all users", 30)
    all_text = b.text()
    ev1 = b.shot("FIX-DEF-03a_admin_all")
    chip("Misleading")
    fake_text = b.text()
    ev2 = b.shot("FIX-DEF-03b_admin_misleading")
    chip("Credible")
    real_text = b.text()
    chip("Images")
    img_text = b.text()
    ev3 = b.shot("FIX-DEF-03c_admin_images")
    ok = ("matching submissions" in fake_text and "matching submissions" in real_text
          and ("No submissions match this filter" in img_text or "matching submissions" in img_text))
    rec("TC-ADM-09-UI", "Admin submissions screen has working filter chips (DEF-03)", "chips narrow the list; total says 'matching submissions'",
        f"all: {'submissions from all users' in all_text}; Misleading: {'matching submissions' in fake_text}; Credible: {'matching submissions' in real_text}; "
        f"Images: {'No submissions match this filter' in img_text or 'matching submissions' in img_text}", f"{ev1}; {ev2}; {ev3}", ok)
finally:
    b.close()
(Path(args.run_dir) / "results_verify_ui.json").write_text(json.dumps(results, indent=1, ensure_ascii=False), encoding="utf-8")
