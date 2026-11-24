"""KhabarNazar full test pass: real HTTP calls against a running (throwaway) backend.

    python tests/full_pass/run_full_pass.py --base-url http://127.0.0.1:8001 --db sqlite:RUN/test.db \
        --run-dir RUN --label sqlite [--groups reg,log,txt,...]

Groups (default: all except rl/lockout, which need a server with the real limits):
  setup reg log txt img dis his adm sec app perf     (bulk server, limits raised)
  rl lockout                                         (server started with --limits real --lockout-minutes 1)
  txtlite imglite                                    (a short subset, for the PostgreSQL repeat)

Calls go to /api/v1 with the same paths, fields and Bearer tokens as lib/api.ts. Real models only:
nothing is mocked here (fault-injected cases live in fault_cases.py). Results are appended to
RUN/results_<label>.json; merge_results.py builds the dated JSON/CSV in this folder.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import hashlib
import io
import json
import re
import statistics
import subprocess
import sys
import time
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import jwt
from PIL import Image, ImageOps
from sqlalchemy import create_engine, text as sql

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from fp_common import BACKEND, HERE, PY, TEST_JWT_SECRET, resolve_db  # noqa: E402

API = "/api/v1"
PASSWORD = "Password123!"
MODEL_VERSIONS = {"xlmr-urdu", "xlmr-roman-urdu", "tfidf-urdu-long-articles"}
UNAVAILABLE = "text-model-unavailable"


class Runner:
    def __init__(self, args):
        self.base = args.base_url.rstrip("/")
        self.label = args.label
        self.run_dir = Path(args.run_dir).resolve()
        self.db_spec = args.db
        self.engine = create_engine(resolve_db(args.db))
        self.uploads = self.run_dir / "uploads"
        self.http = httpx.Client(timeout=httpx.Timeout(240.0, connect=10.0))
        self.results: list[dict] = []
        self.out = self.run_dir / f"results_{self.label}.json"
        self.state_file = self.run_dir / f"state_{self.label}.json"
        self.state = json.loads(self.state_file.read_text(encoding="utf-8")) if self.state_file.exists() else {}
        if self.out.exists():
            self.results = json.loads(self.out.read_text(encoding="utf-8"))
        self.tag = datetime.now().strftime("%H%M%S%f")[:9]  # new accounts get fresh emails on every run

    # ── plumbing ────────────────────────────────────────────────────────────
    def save(self):
        self.out.write_text(json.dumps(self.results, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
        self.state_file.write_text(json.dumps(self.state, indent=1, ensure_ascii=False), encoding="utf-8")

    def rec(self, id_, title, input_, expected, actual, evidence, result, how="Real", group=None, uc=None, extra=None):
        assert result in ("Pass", "Fail", "Blocked", "Known-limitation", "Info"), result
        row = {"id": id_, "title": title, "input": input_, "expected": expected, "actual": actual,
               "evidence": evidence, "result": result, "how": how, "group": group or id_.split("-")[1],
               "use_case": uc, "db": self.label, "time": datetime.now().isoformat(timespec="seconds")}
        if extra:
            row["data"] = extra
        self.results = [r for r in self.results if not (r["id"] == id_ and r["db"] == self.label)]
        self.results.append(row)
        print(f"[{result:16}] {id_:14} {title[:70]}", flush=True)
        self.save()

    def call(self, method, path, token=None, json_=None, files=None, headers=None, api=True, timeout=None):
        h = dict(headers or {})
        if token:
            h["Authorization"] = f"Bearer {token}"
        url = self.base + (API if api else "") + path
        t = time.perf_counter()
        r = self.http.request(method, url, json=json_, files=files, headers=h,
                              timeout=timeout or httpx.Timeout(240.0, connect=10.0))
        latency = time.perf_counter() - t
        try:
            body = r.json()
        except ValueError:
            body = r.content
        return r, body, round(latency, 2)

    def register(self, key, name, email=None):
        email = email or f"fp.{key}.{self.tag}@example.com"
        r, body, _ = self.call("POST", "/auth/register", json_={"name": name, "email": email, "password": PASSWORD})
        if r.status_code == 400:
            r, body, _ = self.call("POST", "/auth/login", json_={"email": email, "password": PASSWORD})
        assert r.status_code in (200, 201), (r.status_code, body)
        self.state[key] = {"email": email, "token": body["access_token"], "id": body["user"]["id"]}
        self.save()
        return self.state[key]

    def set_role(self, email, role):
        env = {"DATABASE_URL": resolve_db(self.db_spec), "JWT_SECRET": TEST_JWT_SECRET, "PYTHONUTF8": "1",
               "SYSTEMROOT": __import__("os").environ.get("SYSTEMROOT", "")}
        p = subprocess.run([str(PY), "scripts/set_user_role.py", email, role], cwd=BACKEND, env=env,
                           capture_output=True, text=True)
        return p.returncode, (p.stdout + p.stderr).strip()[-300:]

    def tok(self, key):
        return self.state[key]["token"]

    def history_ids(self, token):
        ids, skip = [], 0
        while True:
            r, body, _ = self.call("GET", f"/submissions?skip={skip}&limit=100", token)
            ids += [item["id"] for item in body]
            if len(body) < 100:
                return ids, int(r.headers.get("X-Total-Count", -1))
            skip += 100

    def db_scalar(self, query, **params):
        with self.engine.connect() as c:
            return c.execute(sql(query), params).scalar()

    def text_sub(self, key, text_):
        r, body, lat = self.call("POST", "/submissions/text", self.tok(key), {"text": text_})
        assert r.status_code == 201, (r.status_code, body)
        return body

    # ── setup ───────────────────────────────────────────────────────────────
    def g_setup(self):
        admin_empty = None
        self.register("admin", "Full Pass Admin")
        code, out = self.set_role(self.state["admin"]["email"], "admin")
        r, body, _ = self.call("POST", "/auth/login", json_={"email": self.state["admin"]["email"], "password": PASSWORD})
        self.state["admin"]["token"] = body["access_token"]
        r2, subs, _ = self.call("GET", "/admin/submissions", self.tok("admin"))
        admin_empty = {"status": r2.status_code, "items": len(subs) if isinstance(subs, list) else None,
                       "total": r2.headers.get("X-Total-Count")}
        self.state["admin_empty_system"] = admin_empty
        for key, name in (("A", "User A"), ("B", "User B"), ("T", "Text Runner"), ("I", "Image Runner")):
            self.register(key, name)
        self.rec("SETUP-01", "Accounts: users A, B, T, I registered; admin = register + scripts/set_user_role.py (setup guide 12.3)",
                 "POST /auth/register x5; set_user_role.py <admin email> admin", "admin role granted; 201s",
                 f"set_user_role exit {code}; admin role now {body['user']['role']}", f"script output: {out!r}",
                 "Pass" if code == 0 and body["user"]["role"] == "admin" else "Fail", group="SETUP")

    # ── TC-REG ──────────────────────────────────────────────────────────────
    def g_reg(self):
        uc = "UC-1 User Registration"
        email = f"fp.reg.{self.tag}@example.com"
        r, b, _ = self.call("POST", "/auth/register", json_={"name": "Reg User", "email": email, "password": PASSWORD})
        ok = r.status_code == 201 and b.get("access_token") and b["user"]["role"] == "user" and "password" not in json.dumps(b)
        self.rec("TC-REG-01", "Register with valid data", f"name 'Reg User', {email}, valid password", "201, token, role user, no password in body",
                 f"{r.status_code}, role {b.get('user', {}).get('role')}, token {'present' if b.get('access_token') else 'missing'}",
                 f"POST /auth/register -> {r.status_code}", "Pass" if ok else "Fail", uc=uc)
        self.state["reg_body_sample"] = b
        r, b, _ = self.call("POST", "/auth/register", json_={"name": "Reg User", "email": email, "password": PASSWORD})
        self.state["dup_message"] = b.get("detail")
        self.rec("TC-REG-02", "Duplicate email is refused", email + " again", "400 'An account with this email already exists'",
                 f"{r.status_code} {b.get('detail')!r}", f"POST /auth/register -> {r.status_code}",
                 "Pass" if r.status_code == 400 and "already exists" in str(b.get("detail")) else "Fail", uc=uc)
        cases = [("not-an-email", "Reg User", PASSWORD), ("a@b", "Reg User", PASSWORD)]
        res = [self.call("POST", "/auth/register", json_={"name": n, "email": e, "password": p})[0].status_code for e, n, p in cases]
        self.rec("TC-REG-03", "Invalid email format is refused", "'not-an-email', 'a@b'", "422 for both", f"{res}",
                 "POST /auth/register", "Pass" if res == [422, 422] else "Fail", uc=uc)
        cases = {"empty name": {"name": "", "email": f"e1.{self.tag}@example.com", "password": PASSWORD},
                 "blank name": {"name": "   ", "email": f"e2.{self.tag}@example.com", "password": PASSWORD},
                 "empty password": {"name": "Reg", "email": f"e3.{self.tag}@example.com", "password": ""},
                 "5-char password": {"name": "Reg", "email": f"e4.{self.tag}@example.com", "password": "abc12"},
                 "missing email": {"name": "Reg", "password": PASSWORD}}
        res = {k: self.call("POST", "/auth/register", json_=v)[0].status_code for k, v in cases.items()}
        self.rec("TC-REG-04", "Empty fields / too-short password are refused", ", ".join(cases), "422 for every case", json.dumps(res),
                 "POST /auth/register", "Pass" if set(res.values()) == {422} else "Fail", uc=uc)
        # 05 normalisation
        raw = f"  Fp.MixedCase.{self.tag}@Example.COM  "
        r, b, _ = self.call("POST", "/auth/register", json_={"name": "Case User", "email": raw, "password": PASSWORD})
        stored = b.get("user", {}).get("email") if r.status_code == 201 else None
        lower_login = self.call("POST", "/auth/login", json_={"email": raw.strip().lower(), "password": PASSWORD})[0].status_code
        upper_login = self.call("POST", "/auth/login", json_={"email": raw.strip().upper(), "password": PASSWORD})[0].status_code
        ok = r.status_code == 201 and stored == raw.strip().lower() and lower_login == upper_login == 200
        self.rec("TC-REG-05", "Email with mixed case and spaces is normalised", repr(raw), "stored lower-case without spaces; login works in any case",
                 f"register {r.status_code}, stored {stored!r}, login lower {lower_login}, upper {upper_login}",
                 "POST /auth/register, /auth/login", "Pass" if ok else "Fail", uc=uc)
        long_cases = {"name 101 chars": {"name": "N" * 101, "email": f"l1.{self.tag}@example.com", "password": PASSWORD},
                      "email 260 chars": {"name": "Long", "email": "l" * 248 + "@example.com", "password": PASSWORD},
                      "password 73 bytes": {"name": "Long", "email": f"l3.{self.tag}@example.com", "password": "p" * 73},
                      "password 72 bytes (limit)": {"name": "Long", "email": f"l4.{self.tag}@example.com", "password": "p" * 72}}
        res = {k: self.call("POST", "/auth/register", json_=v)[0].status_code for k, v in long_cases.items()}
        ok = res["name 101 chars"] == res["email 260 chars"] == res["password 73 bytes"] == 422 and res["password 72 bytes (limit)"] == 201
        self.rec("TC-REG-06", "Over-long name, email and password", ", ".join(long_cases), "422 over the limits; 72-byte password accepted",
                 json.dumps(res), "POST /auth/register", "Pass" if ok else "Fail", uc=uc)
        name = "محمد علی خان"
        r, b, _ = self.call("POST", "/auth/register", json_={"name": name, "email": f"urdu.{self.tag}@example.com", "password": PASSWORD})
        me = self.call("GET", "/users/me", b.get("access_token"))[1] if r.status_code == 201 else {}
        self.rec("TC-REG-07", "Urdu-script name", name, "201; name returned unchanged by /users/me",
                 f"{r.status_code}; /users/me name {me.get('name')!r}", "POST /auth/register, GET /users/me",
                 "Pass" if r.status_code == 201 and me.get("name") == name else "Fail", uc=uc)
        secret_pw = f"Unique-Pw-{self.tag}-xyz"
        e = f"pwcheck.{self.tag}@example.com"
        bodies = [self.call("POST", "/auth/register", json_={"name": "Pw Check", "email": e, "password": secret_pw})[0].text,
                  self.call("POST", "/auth/login", json_={"email": e, "password": secret_pw})[0].text,
                  self.call("POST", "/auth/login", json_={"email": e, "password": secret_pw + "x"})[0].text,
                  self.call("POST", "/auth/register", json_={"name": "Pw Check", "email": e, "password": secret_pw})[0].text]
        log = (self.run_dir / "server.log").read_text(encoding="utf-8", errors="replace")
        hashed = self.db_scalar("SELECT password_hash FROM users WHERE email = :e", e=e) or ""
        leaks = [i for i, t in enumerate(bodies) if secret_pw in t]
        ok = not leaks and secret_pw not in log and hashed.startswith("$2") and secret_pw not in hashed
        self.rec("TC-REG-08", "The password never appears in a response, the log or the database", "a unique password; register, login, wrong login, duplicate",
                 "absent from all 4 response bodies and server.log; stored as a bcrypt hash",
                 f"found in responses {leaks or 'none'}; in server.log: {secret_pw in log}; DB value is bcrypt ($2…): {hashed.startswith('$2')}",
                 "response bodies, RUN/server.log, users.hashed_password", "Pass" if ok else "Fail", uc=uc)
        msg = str(self.state.get("dup_message"))
        expected = "An account with this email already exists"
        self.rec("TC-REG-09", "Duplicate-email wording vs the use case", "duplicate registration", f"'{expected}'",
                 repr(msg), "TC-REG-02 response detail", "Pass" if msg.rstrip(".") == expected else "Fail", uc=uc)
        self.rec("TC-REG-10", "Where the app goes after registering", "register in the app", "use case: login page or home (record)",
                 "the backend returns a token at registration (auto sign-in); the screen is recorded in TC-UI-03",
                 f"POST /auth/register body keys {sorted(self.state['reg_body_sample'])}", "Info", uc=uc)

    # ── TC-LOG ──────────────────────────────────────────────────────────────
    def g_log(self):
        uc = "UC-2 Login"
        A = self.state["A"]
        r, b, _ = self.call("POST", "/auth/login", json_={"email": A["email"], "password": PASSWORD})
        self.rec("TC-LOG-01", "Login with valid credentials", A["email"], "200 with token and the user's role", f"{r.status_code}, role {b.get('user', {}).get('role')}",
                 "POST /auth/login", "Pass" if r.status_code == 200 and b.get("access_token") else "Fail", uc=uc)
        r1, b1, _ = self.call("POST", "/auth/login", json_={"email": A["email"], "password": "WrongPass999"})
        self.rec("TC-LOG-02", "Wrong password", A["email"] + " / wrong password", "401 'Incorrect email or password entered'", f"{r1.status_code} {b1.get('detail')!r}",
                 "POST /auth/login", "Pass" if r1.status_code == 401 and str(b1.get("detail")).rstrip(".") == "Incorrect email or password entered" else "Fail", uc=uc)
        r2, b2, _ = self.call("POST", "/auth/login", json_={"email": f"nobody.{self.tag}@example.com", "password": PASSWORD})
        self.rec("TC-LOG-03", "Unknown email", "nobody@…", "401, same message", f"{r2.status_code} {b2.get('detail')!r}", "POST /auth/login",
                 "Pass" if r2.status_code == 401 else "Fail", uc=uc)
        res = [self.call("POST", "/auth/login", json_=p)[0].status_code for p in ({"email": "", "password": ""}, {"email": A["email"], "password": ""}, {})]
        self.rec("TC-LOG-04", "Empty fields", "empty email/password; empty password; {}", "422", str(res), "POST /auth/login", "Pass" if set(res) == {422} else "Fail", uc=uc)
        r, b, _ = self.call("GET", "/users/me", A["token"])
        self.rec("TC-LOG-05", "Session token works on a protected route", "GET /users/me with A's token", "200, A's profile", f"{r.status_code} {b.get('email')}",
                 "GET /users/me", "Pass" if r.status_code == 200 and str(b.get("email")).lower() == A["email"].lower() else "Fail", uc=uc)
        paths = [(m, p) for m, p in (("POST", "/auth/forgot-password"), ("POST", "/auth/reset-password"), ("POST", "/auth/password-reset"))]
        res = {p: self.call(m, p, json_={"email": A["email"]})[0].status_code for m, p in paths}
        self.rec("TC-LOG-06", "Password reset", "POST /auth/forgot-password etc.", "a reset flow", f"no such endpoint: {res}",
                 "openapi.json has no reset route", "Known-limitation", uc=uc)
        same = (r1.status_code, b1.get("detail")) == (r2.status_code, b2.get("detail"))
        self.rec("TC-LOG-07", "Wrong password and unknown email give identical errors", "TC-LOG-02 vs TC-LOG-03", "same status and message",
                 f"{r1.status_code}/{b1.get('detail')!r} vs {r2.status_code}/{b2.get('detail')!r}", "responses of 02 and 03", "Pass" if same else "Fail", uc=uc)
        now = datetime.now(timezone.utc)
        expired = jwt.encode({"sub": str(A["id"]), "role": "user", "exp": now - timedelta(minutes=5)}, TEST_JWT_SECRET, algorithm="HS256")
        r, b, _ = self.call("GET", "/users/me", expired)
        self.rec("TC-LOG-09", "Expired token", "JWT signed with the server key, exp 5 min ago", "401", f"{r.status_code} {b.get('detail')!r}", "GET /users/me",
                 "Pass" if r.status_code == 401 else "Fail", uc=uc)
        head, payload, sig = A["token"].split(".")
        tampered = f"{head}.{payload}.{sig[:-4]}{'AAAA' if not sig.endswith('AAAA') else 'BBBB'}"
        forged = jwt.encode({"sub": str(A["id"]), "role": "admin", "exp": now + timedelta(hours=1)}, "a-different-secret-" + "x" * 30, algorithm="HS256")
        none_alg = jwt.encode({"sub": str(A["id"]), "role": "admin"}, None, algorithm="none") if hasattr(jwt, "encode") else ""
        res = {n: self.call("GET", "/users/me", t)[0].status_code for n, t in (("tampered signature", tampered), ("wrong key", forged), ("alg none", none_alg))}
        self.rec("TC-LOG-10", "Tampered JWT signature", "A's token with altered signature; token signed by another key; alg=none", "401 for all", json.dumps(res),
                 "GET /users/me", "Pass" if set(res.values()) == {401} else "Fail", uc=uc)
        D = self.register("D", "Delete Me")
        self.text_sub("D", "حکومت نے آج نیا پل کھول دیا")
        try:
            with self.engine.begin() as c:
                c.execute(sql("DELETE FROM users WHERE id = :i"), {"i": D["id"]})
            deleted = "row deleted"
        except Exception as exc:
            deleted = f"delete failed: {type(exc).__name__}"
        r, b, _ = self.call("GET", "/users/me", D["token"])
        orphans = self.db_scalar("SELECT count(*) FROM submissions WHERE user_id = :i", i=D["id"])
        self.state["delete_user_orphans"] = {"deleted": deleted, "orphan_submissions": orphans}
        self.rec("TC-LOG-11", "A deleted user's token", "register D, submit once, DELETE FROM users (no API for this)", "401",
                 f"{deleted}; /users/me {r.status_code}", "GET /users/me after a direct SQL delete", "Pass" if r.status_code == 401 else "Fail", uc=uc)
        C = self.register("C", "Role Flip")
        before = self.call("GET", "/admin/stats", C["token"])[0].status_code
        self.set_role(C["email"], "admin")
        promoted = self.call("GET", "/admin/stats", C["token"])[0].status_code
        self.set_role(C["email"], "user")
        demoted = self.call("GET", "/admin/stats", C["token"])[0].status_code
        claim = jwt.encode({"sub": str(A["id"]), "role": "admin", "exp": now + timedelta(hours=1)}, TEST_JWT_SECRET, algorithm="HS256")
        claimed = self.call("GET", "/admin/stats", claim)[0].status_code
        ok = (before, promoted, demoted, claimed) == (403, 200, 403, 403)
        self.rec("TC-LOG-12", "Role comes from the database, not the token", "same token before/after promote and demote; token claiming role=admin for user A",
                 "403, 200, 403; claim ignored (403)", f"before {before}, promoted {promoted}, demoted {demoted}, admin claim {claimed}",
                 "GET /admin/stats; scripts/set_user_role.py", "Pass" if ok else "Fail", uc=uc)
        self.rec("TC-LOG-13", "Logout clears the stored token on web", "web app logout", "token removed from browser storage", "covered in TC-UI (browser)",
                 "see TC-UI-16", "Info", uc=uc)
        self.g_spoof(loopback=True)

    def g_spoof(self, loopback=False):
        """TC-LOG-14. Run against a non-loopback address too: uvicorn's default --proxy-headers trusts
        X-Forwarded-For only from 127.0.0.1, so a loopback client is a trusted proxy by design."""
        E = self.register("E" + ("lo" if loopback else "lan"), "Spoof Target")
        statuses = []
        for i in range(6):
            statuses.append(self.call("POST", "/auth/login", json_={"email": E["email"], "password": "wrong-pass"},
                                      headers={"X-Forwarded-For": f"203.0.113.{i + 1}"})[0].status_code)
        ok = statuses[:5] == [401] * 5 and statuses[5] == 429
        where = "from 127.0.0.1 (uvicorn trusts loopback proxies by default)" if loopback else f"from a LAN address ({self.base})"
        self.rec("TC-LOG-14" + ("-loopback" if loopback else ""), f"Spoofed X-Forwarded-For vs the login limiter (TRUST_PROXY_HEADERS off), client {where}",
                 "6 wrong logins for one account, each with a different X-Forwarded-For", "5x 401 then 429", str(statuses),
                 f"POST /auth/login {where}", ("Pass" if ok else "Fail") if not loopback else "Info", uc="UC-2 Login")

    # ── TC-TXT ──────────────────────────────────────────────────────────────
    def g_txt(self, subset=None):
        from app.ai.text.preprocess import clean_urdu_notebook

        inputs = json.loads((HERE / "text_inputs.json").read_text(encoding="utf-8"))
        if subset:
            inputs = [i for i in inputs if i["id"] in subset]
        token = self.tok("T")
        for item in inputs:
            exp = item["expected"]
            ids_before, total_before = self.history_ids(token)
            runs = []
            repeat = 1 if exp["outcome"] == "rejected_422" else 2
            for _ in range(repeat):
                r, b, lat = self.call("POST", "/submissions/text", token, {"text": item["text"]})
                runs.append((r.status_code, b, lat))
            status, body, lat = runs[0]
            ids_after, total_after = self.history_ids(token)
            fails, findings = [], []
            d = {"http_status": status, "latency_s": lat, "latency_repeat_s": runs[1][2] if repeat == 2 else None}
            if status >= 500:
                fails.append(f"server error {status}")
            if exp["outcome"] == "rejected_422":
                if status != 422:
                    fails.append(f"expected 422, got {status}")
                d["error"] = body.get("detail") if isinstance(body, dict) else str(body)[:200]
                if total_after != total_before:
                    fails.append("history count changed after a rejected input")
                d["in_history"] = total_after != total_before
            elif status != 201:
                fails.append(f"expected 201, got {status}: {str(body)[:200]}")
            else:
                ts, ex = body["text_submission"], body["explainability"] or {}
                label, conf, risk = body["final_label"], ts["text_confidence"], body["combined_risk_score"]
                words = json.loads(ex.get("highlighted_words") or "[]")
                d.update({"detected_language": body["detected_language"], "model_version": ex.get("model_version"),
                          "label": label, "confidence": conf, "risk": risk,
                          "highlights": [(w["word"], w["contribution"]) for w in words],
                          "summary": ex.get("explanation_summary"), "submission_id": body["id"],
                          "stored_text_equal": ts["input_text"] == item["text"].strip()})
                if exp["model_version"] and ex.get("model_version") != exp["model_version"]:
                    fails.append(f"route {ex.get('model_version')} != expected {exp['model_version']}")
                if exp["detected_language"] and body["detected_language"] != exp["detected_language"]:
                    fails.append(f"language {body['detected_language']} != expected {exp['detected_language']}")
                if exp["outcome"] == "uncertain_no_score" and (label != "Uncertain" or conf is not None or risk is not None):
                    fails.append(f"expected Uncertain with no score, got {label} {conf}")
                if label in ("Real", "Fake"):
                    if ex.get("model_version") not in MODEL_VERSIONS:
                        fails.append("verdict without a known model")
                    if conf is None or not 0 <= conf <= 1:
                        fails.append(f"confidence {conf} outside 0-1")
                    fake_p = conf if label == "Fake" else 1 - conf
                    if risk is None or abs(risk - fake_p) > 1e-3 or (label == "Real" and risk >= 0.5) or (label == "Fake" and risk < 0.5):
                        fails.append(f"risk {risk} inconsistent with {label} {conf}")
                    truncated_note = "only its first part was checked" in (ex.get("explanation_summary") or "")
                    if not (1 <= len(words) <= 8 or (truncated_note and not words)):
                        fails.append(f"{len(words)} highlighted words (expected 1-8; 0 only when the summary says the text was truncated)")
                    norm_in = clean_urdu_notebook(item["text"]).casefold()
                    raw_in = unicodedata.normalize("NFKC", item["text"]).casefold()
                    foreign = [w["word"] for w in words if w["word"].casefold() not in raw_in and w["word"].casefold() not in norm_in]
                    if foreign:
                        fails.append(f"highlighted words not in the input: {foreign}")
                else:
                    if conf is not None or risk is not None:
                        fails.append("a score was given with an Uncertain/unavailable result")
                    if words:
                        fails.append("highlights shown although no model ran")
                summary = ex.get("explanation_summary") or ""
                if not summary.strip():
                    fails.append("empty summary")
                for phrase in exp["disclosure"]:
                    if phrase.casefold() not in summary.casefold():
                        fails.append(f"missing disclosure {phrase!r}")
                in_hist = body["id"] in ids_after
                d["in_history"] = in_hist
                if not in_hist:
                    fails.append("accepted input missing from history")
                if repeat == 2:
                    s2, b2, _ = runs[1]
                    same = s2 == 201 and b2["final_label"] == label and b2["text_submission"]["text_confidence"] == conf \
                        and b2["combined_risk_score"] == risk and (b2["explainability"] or {}).get("highlighted_words") == ex.get("highlighted_words")
                    d["deterministic"] = same
                    if not same:
                        fails.append("second submission gave a different result")
                if not d["stored_text_equal"]:
                    fails.append("stored text differs from the submitted text (after trimming)")
                if label == "Uncertain" and ex.get("model_version") in MODEL_VERSIONS:
                    findings.append("Uncertain from a model")
            result = "Fail" if fails else "Pass"
            if not fails and item["category"] == "english":
                result = "Known-limitation"  # limitation 4: English goes through the Roman Urdu model
            exp_text = f"{exp['outcome']}; route {exp['model_version']}; language {exp['detected_language']}; disclosure {exp['disclosure']}"
            act = (f"{status}; {d.get('detected_language')}; {d.get('model_version')}; {d.get('label')} conf {d.get('confidence')} risk {d.get('risk')}; "
                   f"{len(d.get('highlights') or [])} highlights; {lat}s" if status == 201 else f"{status}; {d.get('error')}")
            preview = item["text"] if len(item["text"]) <= 120 else item["text"][:110] + f"… ({len(item['text'])} chars)"
            self.rec(f"TC-TXT-{item['id']}", f"{item['category']}: {item['note'] or item['id']}", preview, exp_text, act,
                     f"POST /api/v1/submissions/text x{repeat}; history before/after {total_before}->{total_after}",
                     result, uc="UC-3 Submit Text", extra={**d, "failures": fails, "report_tc": item.get("report_tc"), "category": item["category"]})
        self.save()

    # ── TC-IMG / TC-OCR / TC-GC (HTTP side) ────────────────────────────────
    def g_img(self, subset=None):
        manifest = json.loads((HERE / "images" / "manifest.json").read_text(encoding="utf-8"))
        if subset:
            manifest = [m for m in manifest if m["id"] in subset]
        token, tok_b = self.tok("I"), self.tok("B")
        for m in manifest:
            path = HERE / "images" / m["file"]
            data = path.read_bytes()
            exp = m["expected"]
            _, total_before = self.history_ids(token)
            files_before = len(list(self.uploads.glob("*.*"))) if self.uploads.exists() else None
            r, b, lat = self.call("POST", "/submissions/image", token, files={"file": (m["file"], data, m["content_type"])})
            _, total_after = self.history_ids(token)
            files_after = len(list(self.uploads.glob("*.*"))) if self.uploads.exists() else None
            fails, d = [], {"http_status": r.status_code, "latency_s": lat}
            if r.status_code >= 500:
                fails.append(f"server error {r.status_code}")
            if r.status_code != exp["http_status"]:
                fails.append(f"expected {exp['http_status']}, got {r.status_code}: {str(b)[:160]}")
            if r.status_code != 201:
                d["error"] = b.get("detail") if isinstance(b, dict) else str(b)[:200]
                if total_after != total_before:
                    fails.append("rejected upload appears in history")
                if files_before is not None and files_after != files_before:
                    fails.append("rejected upload left a file on disk")
            else:
                im, ex = b["image_submission"], b["explainability"] or {}
                d.update({k: im.get(k) for k in ("analysis_branch", "ocr_status", "ocr_text", "ocr_confidence", "detected_language",
                                                 "text_prediction", "text_confidence", "image_score", "manipulation_prediction",
                                                 "image_analysis_status", "text_classification_status", "mime_type", "original_filename")})
                d.update({"final_label": b["final_label"], "risk": b["combined_risk_score"], "gradcam_status": b["gradcam_status"],
                          "model_version": ex.get("model_version"), "summary": ex.get("explanation_summary"), "submission_id": b["id"],
                          "highlights": json.loads(ex.get("highlighted_words") or "[]")})
                if d["image_score"] is None or d["image_analysis_status"] != "completed":
                    fails.append(f"no image score (status {d['image_analysis_status']})")
                for key in ("analysis_branch", "ocr_status", "mime_type", "final_label"):
                    if key in exp and d.get(key) != exp[key]:
                        fails.append(f"{key} {d.get(key)!r} != expected {exp[key]!r}")
                if "combined_risk_score" in exp and d["risk"] != exp["combined_risk_score"]:
                    fails.append(f"risk {d['risk']} != expected {exp['combined_risk_score']}")
                if d["analysis_branch"] == "ai_or_real" and (d["final_label"] != "Uncertain" or d["risk"] is not None):
                    fails.append("no usable text but a verdict/risk was given")
                if d["analysis_branch"] == "image_pair" and d["text_prediction"] in ("Real", "Fake"):
                    fake_p = d["text_confidence"] if d["text_prediction"] == "Fake" else 1 - d["text_confidence"]
                    if d["risk"] is None or abs(d["risk"] - fake_p) > 1e-3:
                        fails.append(f"risk {d['risk']} is not the text's fake probability {fake_p:.4f} (image mixed in?)")
                if "route" in exp and not str(d["model_version"]).endswith(exp["route"]):
                    fails.append(f"OCR text route {d['model_version']} != {exp['route']}")
                if exp.get("disclosure") == "English" and "less reliable" not in (d["summary"] or ""):
                    fails.append("no English disclosure for OCR text")
                if exp.get("reading_order"):
                    pos = [(d["ocr_text"] or "").find(w) for w in exp["reading_order"]]
                    d["reading_order_positions"] = pos
                    if -1 in pos or pos != sorted(pos):
                        fails.append(f"multi-line text not in order: {pos}")
                if exp.get("ocr_reads_upright") and not re.search(r"[\u0600-\u06ff]{3}", d["ocr_text"] or ""):
                    fails.append("EXIF-rotated Urdu text was not read")
                ri, bi, _ = self.call("GET", f"/submissions/{b['id']}/image", token)
                d["original_sha_match"] = ri.status_code == 200 and hashlib.sha256(ri.content).hexdigest() == m["sha256"]
                if not d["original_sha_match"]:
                    fails.append(f"downloaded original differs (status {ri.status_code})")
                rh, bh, _ = self.call("GET", f"/submissions/{b['id']}/heatmap", token)
                d["heatmap_http"] = rh.status_code
                if b["gradcam_status"] == "completed":
                    hm = Image.open(io.BytesIO(rh.content))
                    upright = ImageOps.exif_transpose(Image.open(io.BytesIO(data)))
                    d["heatmap_size"], d["upright_size"] = hm.size, upright.size
                    if hm.size != upright.size:
                        fails.append(f"heatmap {hm.size} != upright image {upright.size}")
                    if "ResNet18" not in (d["summary"] or "") or "other two models" not in (d["summary"] or ""):
                        fails.append("Grad-CAM caption does not say it is ResNet18-only")
                elif rh.status_code != 404:
                    fails.append(f"no heatmap but /heatmap returned {rh.status_code}")
                ob = [self.call("GET", f"/submissions/{b['id']}{p}", tok_b)[0].status_code for p in ("", "/image", "/heatmap")]
                d["user_b_access"] = ob
                if ob != [404, 404, 404]:
                    fails.append(f"user B could read A's submission/image/heatmap: {ob}")
                if total_after != total_before + 1:
                    fails.append("accepted upload not in history")
            result = "Fail" if fails else "Pass"
            act = (f"{r.status_code}; branch {d.get('analysis_branch')}; ocr {d.get('ocr_status')} conf {d.get('ocr_confidence')}; "
                   f"text {d.get('text_prediction')}; final {d.get('final_label')} risk {d.get('risk')}; image_score {d.get('image_score')} "
                   f"({d.get('manipulation_prediction')}); gradcam {d.get('gradcam_status')}; {lat}s" if r.status_code == 201
                   else f"{r.status_code}; {d.get('error')}")
            self.rec(f"TC-IMG-{m['id']}", f"{m['category']}: {m['how_made'][:80]}", m["file"], json.dumps(exp, ensure_ascii=False), act,
                     f"POST /submissions/image ({m['content_type']}, {m['bytes']} B); GET image/heatmap; user B access",
                     result, uc="UC-4 Submit Image", extra={**d, "failures": fails, "report_tc": m.get("report_tc"), "file": m["file"]})

    # ── TC-DIS ──────────────────────────────────────────────────────────────
    def g_dis(self):
        uc = "UC-6 Dispute AI Prediction"
        A, adm = self.tok("A"), self.tok("admin")
        subs = [self.text_sub("A", f"حکومت نے آج نمبر {i} سڑک کھولنے کا اعلان کیا ہے") for i in range(8)]
        self.state["A_subs"] = [s["id"] for s in subs]
        unc = self.call("POST", "/submissions/text", A, {"text": "1234567890"})[1]
        sid = lambda i: subs[i]["id"]  # noqa: E731

        def dis(i_or_id, just, link=..., token=A):
            payload = {"submission_id": i_or_id if i_or_id > 100000 or i_or_id < 0 else i_or_id, "justification": just}
            if link is not ...:
                payload["evidence_link"] = link
            return self.call("POST", "/disputes", token, payload)

        r, b, _ = dis(sid(0), "The news is wrong; the road opened last year.", "https://example.com/report")
        self.state["dispute_main"] = b.get("id")
        self.rec("TC-DIS-01", "Submit a valid dispute", "justification 45 chars + https link", "201, status pending", f"{r.status_code} {b.get('status')}",
                 "POST /disputes", "Pass" if r.status_code == 201 and b.get("status") == "pending" else "Fail", uc=uc)
        r, b, _ = dis(sid(1), "")
        self.rec("TC-DIS-02", "Empty justification", "''", "422 ('Please provide a justification…')", f"{r.status_code} {str(b.get('detail'))[:160]}",
                 "POST /disputes", "Pass" if r.status_code == 422 else "Fail", uc=uc)
        r, b, _ = dis(sid(1), "This is clearly wrong news.", "not a url at all")
        self.rec("TC-DIS-03", "Invalid evidence link", "'not a url at all'", "422 ('Please enter a valid URL…')", f"{r.status_code} {str(b.get('detail'))[:200]}",
                 "POST /disputes", "Pass" if r.status_code == 422 else "Fail", uc=uc)
        other = self.text_sub("B", "حکومت نے آج بی کی خبر دی")
        r, b, _ = dis(other["id"], "Trying to dispute someone else's result.")
        self.rec("TC-DIS-04", "Dispute another user's submission", "user B's submission id", "404", f"{r.status_code} {b.get('detail')!r}",
                 "POST /disputes", "Pass" if r.status_code == 404 else "Fail", uc=uc)
        res = {"9 chars": dis(sid(1), "123456789")[0].status_code, "10 spaces+9": dis(sid(1), "    abcdefghi    ")[0].status_code,
               "exactly 10": dis(sid(1), "abcdefghij")[0].status_code, "5001 chars": dis(sid(2), "x" * 5001)[0].status_code,
               "5000 chars": dis(sid(2), "y" * 5000)[0].status_code}
        ok = res == {"9 chars": 422, "10 spaces+9": 422, "exactly 10": 201, "5001 chars": 422, "5000 chars": 201}
        self.rec("TC-DIS-05", "Justification length limits", ", ".join(res), "9 -> 422, padded 9 -> 422, 10 -> 201, 5000 -> 201, 5001 -> 422", json.dumps(res),
                 "POST /disputes", "Pass" if ok else "Fail", uc=uc)
        links = {"blank ''": ("", 201, 3), "missing": (..., 201, 4), "javascript:": ("javascript:alert(1)", 422, 5),
                 "data:": ("data:text/html,<b>x</b>", 422, 5), "ftp:": ("ftp://files.example.com/a.txt", 422, 5),
                 "malformed http://": ("http://", 422, 5), "no dot host": ("https://localhost/x", 422, 5), "with space": ("https://exa mple.com", 422, 5),
                 "no scheme": ("geo.tv/news/12345", 201, 6)}
        res, stored = {}, None
        for name, (link, want, idx) in links.items():
            r, b, _ = dis(sid(idx), "Evidence link test case.", link)
            res[name] = r.status_code
            if name == "no scheme" and r.status_code == 201:
                stored = b.get("evidence_link")
            if r.status_code == 201 and name in ("blank ''",):
                self.state["blank_link_value"] = b.get("evidence_link")
        ok = all(res[n] == want for n, (_, want, _) in links.items()) and stored == "https://geo.tv/news/12345"
        self.rec("TC-DIS-06", "Evidence-link rules", ", ".join(links), "blank/missing allowed; javascript:/data:/ftp:/malformed rejected; no scheme -> https://",
                 f"{json.dumps(res)}; 'geo.tv/news/12345' stored as {stored!r}; blank stored as {self.state.get('blank_link_value')!r}",
                 "POST /disputes", "Pass" if ok else "Fail", uc=uc)
        r, b, _ = dis(unc["id"], "The result is Uncertain but I know it is false.")
        self.state["dispute_uncertain"] = b.get("id")
        self.rec("TC-DIS-07", "Dispute an Uncertain result", f"submission {unc['id']} (digits only -> Uncertain)", "201", f"{r.status_code}",
                 "POST /disputes", "Pass" if r.status_code == 201 else "Fail", uc=uc)
        dup = dis(sid(0), "Second dispute while the first is pending.")
        rv = self.call("PATCH", f"/disputes/{self.state['dispute_main']}", adm, {"admin_decision": "uphold_ai", "admin_comment": "Checked; the AI result stands."})
        again = dis(sid(0), "New evidence after the first review was done.", "https://example.com/new")
        self.state["dispute_after_review"] = again[1].get("id")
        ok = dup[0].status_code == 409 and rv[0].status_code == 200 and again[0].status_code == 201
        self.rec("TC-DIS-08", "One pending dispute per submission; a new one allowed after review", "dispute twice; admin reviews; dispute again",
                 "409 while pending; 201 after review", f"while pending {dup[0].status_code} {dup[1].get('detail')!r}; review {rv[0].status_code}; after review {again[0].status_code}",
                 "POST /disputes, PATCH /disputes/{id}", "Pass" if ok else "Fail", uc=uc)
        lst = self.call("GET", "/submissions?limit=100", A)[1]
        counts = {i["id"]: i["dispute_count"] for i in lst}
        mine = self.call("GET", "/disputes?limit=100", A)[1]
        st = {x["id"]: x["status"] for x in mine}
        ok = counts.get(sid(0)) == 2 and st.get(self.state["dispute_main"]) == "reviewed" and st.get(self.state["dispute_after_review"]) == "pending"
        self.rec("TC-DIS-09", "Dispute status in history and the user's dispute list", "GET /submissions, GET /disputes as A",
                 "dispute_count 2 on that submission; first reviewed, second pending",
                 f"dispute_count {counts.get(sid(0))}; statuses {st.get(self.state['dispute_main'])}/{st.get(self.state['dispute_after_review'])}",
                 "GET /submissions, GET /disputes", "Pass" if ok else "Fail", uc=uc)

    # ── TC-HIS ──────────────────────────────────────────────────────────────
    def g_his(self):
        uc = "UC-7 View Submission History"
        A, B = self.tok("A"), self.tok("B")
        r, b, _ = self.call("GET", "/submissions", A)
        newest_first = [x["created_at"] for x in b] == sorted([x["created_at"] for x in b], reverse=True)
        self.rec("TC-HIS-01", "User sees their own history, newest first, with a total", "GET /submissions as A", "200, A's items only, X-Total-Count",
                 f"{r.status_code}, {len(b)} items, total {r.headers.get('X-Total-Count')}, newest first {newest_first}",
                 "GET /submissions", "Pass" if r.status_code == 200 and newest_first and r.headers.get("X-Total-Count") else "Fail", uc=uc)
        a_ids = set(self.history_ids(A)[0])
        b_ids = set(self.history_ids(B)[0])
        probe = sorted(a_ids)[:3]
        cross = [self.call("GET", f"/submissions/{i}", B)[0].status_code for i in probe]
        ok = not (a_ids & b_ids) and set(cross) == {404}
        self.rec("TC-HIS-02", "Another user's records are not visible", "B lists history; B opens 3 of A's ids", "no overlap; 404s",
                 f"overlap {len(a_ids & b_ids)}; B opening A's ids -> {cross}", "GET /submissions, GET /submissions/{id}", "Pass" if ok else "Fail", uc=uc)
        F = self.register("F", "Fresh User")
        r, b, _ = self.call("GET", "/submissions", F["token"])
        self.rec("TC-HIS-03", "Empty history", "new user", "200 [] total 0 (app: 'You have not submitted any content yet')",
                 f"{r.status_code} {b} total {r.headers.get('X-Total-Count')}", "GET /submissions", "Pass" if b == [] and r.headers.get("X-Total-Count") == "0" else "Fail", uc=uc)
        res = {q: self.call("GET", f"/submissions?{q}", A)[0].status_code for q in ("limit=0", "limit=101", "limit=-1", "skip=-1", "limit=abc")}
        page1 = [x["id"] for x in self.call("GET", "/submissions?skip=0&limit=3", A)[1]]
        page2 = [x["id"] for x in self.call("GET", "/submissions?skip=3&limit=3", A)[1]]
        beyond = self.call("GET", "/submissions?skip=100000&limit=5", A)[1]
        ok = set(res.values()) == {422} and len(page1) == 3 and not set(page1) & set(page2) and beyond == [] and \
            self.call("GET", "/submissions?limit=100", A)[0].status_code == 200
        self.rec("TC-HIS-04", "Paging with skip/limit and its limits", "limit 0/101/-1, skip -1, limit abc; two pages of 3; skip beyond the end",
                 "422 for invalid values; disjoint pages; [] beyond the end", f"{json.dumps(res)}; page1 {page1}; page2 {page2}; beyond {beyond}",
                 "GET /submissions", "Pass" if ok else "Fail", uc=uc)
        I = self.tok("I")
        items = self.call("GET", "/submissions?limit=100", I)[1]
        img = next((x for x in items if x["has_image"]), None)
        detail = self.call("GET", f"/submissions/{img['id']}", I)[1] if img else {}
        ti = self.call("GET", "/submissions?limit=5", self.tok("T"))[1]
        ok = img and detail.get("image_submission", {}).get("image_score") is not None and "ocr_status" in detail["image_submission"] \
            and ti and ti[0].get("text_preview")
        self.rec("TC-HIS-05", "Text and image items carry their details", "history list + detail of an image item; text preview",
                 "list: has_image / text_preview; detail: OCR text, ocr_status, image_score",
                 f"image item {img and img['id']}: ocr_status {detail.get('image_submission', {}).get('ocr_status')}, image_score {detail.get('image_submission', {}).get('image_score')}; "
                 f"text preview present {bool(ti and ti[0].get('text_preview'))}", "GET /submissions, /submissions/{id}", "Pass" if ok else "Fail", uc=uc)
        rej = [r for r in self.results if r["id"].startswith(("TC-TXT-X0", "TC-IMG-F")) and r.get("data", {}).get("http_status") in (413, 415, 422)]
        leaked = [r["id"] for r in rej if r["data"].get("in_history") or any("history" in f for f in r["data"].get("failures", []))]
        self.rec("TC-HIS-06", "Rejected submissions are never saved", f"{len(rej)} rejected text/image inputs from TC-TXT/TC-IMG",
                 "none in history", f"in history: {leaked or 'none'}", "history counts before/after each rejected request",
                 "Pass" if rej and not leaked else ("Blocked" if not rej else "Fail"), uc=uc)

    # ── TC-ADM ──────────────────────────────────────────────────────────────
    def g_adm(self):
        uc_rev, uc_all = "UC-8 Admin Reviews Dispute", "UC-9 Admin Views All Submissions"
        adm, A, B = self.tok("admin"), self.tok("A"), self.tok("B")
        r, b, _ = self.call("GET", "/admin/submissions?limit=100", adm)
        emails, skip = set(), 0
        while True:
            page = self.call("GET", f"/admin/submissions?skip={skip}&limit=100", adm)[1]
            emails |= {str(x.get("user_email")).lower() for x in page}
            if len(page) < 100:
                break
            skip += 100
        self.rec("TC-ADM-01", "Admin lists all submissions", "GET /admin/submissions", "200; every user's items with the submitter's email",
                 f"{r.status_code}; {len(b)} on page; total {r.headers.get('X-Total-Count')}; A's and B's emails present (all pages) {self.state['A']['email'].lower() in emails and self.state['B']['email'].lower() in emails}",
                 "GET /admin/submissions (paged)", "Pass" if r.status_code == 200 and self.state["A"]["email"].lower() in emails and self.state["B"]["email"].lower() in emails else "Fail", uc=uc_all)

        st = self.call("GET", "/admin/stats", adm)[1]
        db = {"users": self.db_scalar("SELECT count(*) FROM users"), "submissions": self.db_scalar("SELECT count(*) FROM submissions"),
              "overrides": self.db_scalar("SELECT count(*) FROM submissions WHERE final_label_source = 'Admin'"),
              "disputes": self.db_scalar("SELECT count(*) FROM disputes"), "pending": self.db_scalar("SELECT count(*) FROM disputes WHERE status = 'pending'")}
        api = {"users": st["users"], "submissions": st["submissions"], "overrides": st["admin_overrides"],
               "disputes": st["disputes"]["total"], "pending": st["disputes"]["pending"]}
        self.rec("TC-ADM-02", "Dashboard counts match the database", "GET /admin/stats vs SQL counts", "identical", f"API {api}; DB {db}",
                 "GET /admin/stats; SELECT count(*)", "Pass" if api == db else "Fail", uc=uc_all)
        r, b, _ = self.call("GET", "/disputes?status=pending&limit=100", adm)
        ids = {x["id"] for x in b}
        ok = r.status_code == 200 and self.state["dispute_uncertain"] in ids and all(x["status"] == "pending" for x in b)
        self.rec("TC-ADM-03", "Admin dispute queue (pending filter)", "GET /disputes?status=pending", "only pending disputes, from all users",
                 f"{r.status_code}; {len(b)} pending; contains A's dispute {self.state['dispute_uncertain'] in ids}", "GET /disputes", "Pass" if ok else "Fail", uc=uc_rev)
        subs = self.state["A_subs"]
        disputes = {}
        for i, label in ((3, "Fake"), (4, "Real"), (5, "Uncertain")):
            pending = [x for x in self.call("GET", "/disputes?status=pending&limit=100", A)[1] if x["submission_id"] == subs[i]]
            disputes[label] = pending[0]["id"] if pending else self.call("POST", "/disputes", A, {"submission_id": subs[i], "justification": f"Please re-check, should be {label}."})[1]["id"]
        r, b, _ = self.call("PATCH", f"/disputes/{self.state['dispute_after_review']}", adm, {"admin_decision": "uphold_ai", "admin_comment": "Upheld after a second look."})
        self.rec("TC-ADM-04", "Admin upholds the AI result", "uphold_ai + comment", "200; status reviewed; label unchanged",
                 f"{r.status_code} status {b.get('status')}", "PATCH /disputes/{id}", "Pass" if r.status_code == 200 and b.get("status") == "reviewed" else "Fail", uc=uc_rev)
        res = {}
        for label, did in disputes.items():
            r, b, _ = self.call("PATCH", f"/disputes/{did}", adm, {"admin_decision": "override", "admin_comment": f"Overridden to {label} by the reviewer.", "override_label": label})
            sub = self.call("GET", f"/submissions/{b.get('submission_id')}", A)[1]
            res[label] = (r.status_code, sub.get("final_label"), sub.get("final_label_source"), sub.get("admin_comment"))
        ok = all(v[0] == 200 and v[1] == k and v[2] == "Admin" and v[3] for k, v in res.items())
        self.rec("TC-ADM-05", "Override to each label; the user sees it as the admin's, with the comment", "override to Fake, Real, Uncertain",
                 "200; user's detail: final_label = override, source Admin, admin_comment shown", json.dumps(res, ensure_ascii=False),
                 "PATCH /disputes/{id}; GET /submissions/{id} as the owner", "Pass" if ok else "Fail", uc=uc_rev)
        hist = {x["id"]: (x["final_label"], x["final_label_source"]) for x in self.call("GET", "/submissions?limit=100", A)[1]}
        ok = all(hist.get(subs[i]) == (lbl, "Admin") for i, lbl in ((3, "Fake"), (4, "Real"), (5, "Uncertain")))
        self.rec("TC-HIS-07", "Admin override shows in the user's history list", "GET /submissions as A after the overrides", "final_label + source Admin on the 3 items",
                 str({i: hist.get(subs[i]) for i in (3, 4, 5)}), "GET /submissions", "Pass" if ok else "Fail", uc="UC-7 View Submission History")
        routes = [("GET", "/admin/submissions", None), ("GET", "/admin/stats", None),
                  ("PATCH", f"/disputes/{self.state['dispute_uncertain']}", {"admin_decision": "uphold_ai", "admin_comment": "user trying"})]
        res = {f"{m} {p}": self.call(m, p, A, j)[0].status_code for m, p, j in routes}
        self.rec("TC-ADM-06", "A non-admin gets 403 on every admin route", "user A token", "403 everywhere", json.dumps(res),
                 "GET /admin/*, PATCH /disputes/{id}", "Pass" if set(res.values()) == {403} else "Fail", uc=uc_rev)
        r, b, _ = self.call("PATCH", f"/disputes/{disputes['Fake']}", adm, {"admin_decision": "uphold_ai", "admin_comment": "second review"})
        self.rec("TC-ADM-07", "A reviewed dispute cannot be reviewed again", "PATCH an already reviewed dispute", "409", f"{r.status_code} {b.get('detail')!r}",
                 "PATCH /disputes/{id}", "Pass" if r.status_code == 409 else "Fail", uc=uc_rev)
        pend = self.state["dispute_uncertain"]
        res = {"no comment": self.call("PATCH", f"/disputes/{pend}", adm, {"admin_decision": "uphold_ai"}),
               "2-char comment": self.call("PATCH", f"/disputes/{pend}", adm, {"admin_decision": "uphold_ai", "admin_comment": "ok"}),
               "whitespace comment": self.call("PATCH", f"/disputes/{pend}", adm, {"admin_decision": "uphold_ai", "admin_comment": "     "}),
               "override without label": self.call("PATCH", f"/disputes/{pend}", adm, {"admin_decision": "override", "admin_comment": "missing label"})}
        summary = {k: (v[0].status_code, str(v[1].get("detail"))[:90]) for k, v in res.items()}
        self.rec("TC-ADM-08", "Review needs a comment (use case 4-A)", ", ".join(res), "422 for each ('Please add a comment…')",
                 json.dumps(summary, ensure_ascii=False), "PATCH /disputes/{id}", "Pass" if all(v[0] == 422 for v in summary.values()) else "Fail", uc=uc_rev)
        params = {q: self.call("GET", f"/admin/submissions?{q}", adm) for q in ("final_label=Fake", "submission_type=image", "user_email=x")}
        totals = {q: v[0].headers.get("X-Total-Count") for q, v in params.items()}
        base_total = self.call("GET", "/admin/submissions", adm)[0].headers.get("X-Total-Count")
        filtered = any(t != base_total for t in totals.values())
        self.rec("TC-ADM-09", "Filtering the all-submissions list (use case promise)", "?final_label=Fake, ?submission_type=image, ?user_email=x",
                 "a filter exists", f"totals {totals} vs unfiltered {base_total}: parameters {'are applied' if filtered else 'are ignored (no filter)'}; disputes support ?status=",
                 "GET /admin/submissions; openapi", "Pass" if filtered else "Fail", uc=uc_all)
        e = self.state.get("admin_empty_system") or {}
        self.rec("TC-ADM-10", "No submissions recorded yet", "GET /admin/submissions on an empty system (captured at setup)",
                 "empty list (app: 'No submissions have been recorded yet')", json.dumps(e), "GET /admin/submissions before any check",
                 "Pass" if e.get("items") == 0 and e.get("total") == "0" else "Blocked", uc=uc_all)
        img_sub = next((r["data"]["submission_id"] for r in self.results if r["id"].startswith("TC-IMG-C") and r.get("data", {}).get("gradcam_status") == "completed" and r["db"] == self.label), None)
        res = {}
        if img_sub:
            res = {p or "detail": self.call("GET", f"/submissions/{img_sub}{p}", adm)[0].status_code for p in ("", "/image", "/heatmap")}
        self.rec("TC-ADM-11", "Admin can open any submission's explanation, image and heatmap", f"admin opens user I's image submission {img_sub}", "200 x3",
                 json.dumps(res), "GET /submissions/{id}[/image|/heatmap]", "Pass" if res and set(res.values()) == {200} else "Blocked" if not img_sub else "Fail", uc=uc_all)

    def g_adm01(self):
        """Re-run of TC-ADM-01 only (the first version compared emails case-sensitively on one page)."""
        adm = self.tok("admin")
        uc_all = "UC-9 Admin Views All Submissions"
        r, b, _ = self.call("GET", "/admin/submissions?limit=100", adm)
        emails, skip = set(), 0
        while True:
            page = self.call("GET", f"/admin/submissions?skip={skip}&limit=100", adm)[1]
            emails |= {str(x.get("user_email")).lower() for x in page}
            if len(page) < 100:
                break
            skip += 100
        ok = r.status_code == 200 and self.state["A"]["email"].lower() in emails and self.state["B"]["email"].lower() in emails
        self.rec("TC-ADM-01", "Admin lists all submissions", "GET /admin/submissions (all pages)", "200; every user's items with the submitter's email",
                 f"{r.status_code}; total {r.headers.get('X-Total-Count')}; {len(emails)} distinct submitters; A and B present {ok}",
                 "GET /admin/submissions (paged)", "Pass" if ok else "Fail", uc=uc_all)

    # ── TC-SEC ──────────────────────────────────────────────────────────────
    def g_sec(self):
        spec = self.call("GET", "/openapi.json", api=False)[1]
        public = {"/", "/health", "/api/v1/auth/register", "/api/v1/auth/login", "/auth/register", "/auth/login"}
        res = {}
        for path, ops in spec["paths"].items():
            if path in public:
                continue
            for method in ops:
                p = re.sub(r"\{[^}]+\}", "1", path)
                r = self.http.request(method.upper(), self.base + p, json={} if method in ("post", "patch") else None)
                res[f"{method.upper()} {path}"] = r.status_code
        bad = {k: v for k, v in res.items() if v != 401}
        self.rec("TC-SEC-01", "Every protected endpoint needs a token", f"{len(res)} method/path pairs from /openapi.json, no Authorization header",
                 "401 for all", f"non-401: {bad or 'none'}", "requests without a token", "Pass" if not bad else "Fail", group="SEC")
        I, B = self.tok("I"), self.tok("B")
        own = next((r["data"]["submission_id"] for r in self.results if r["id"].startswith("TC-IMG-C") and r.get("data", {}).get("gradcam_status") == "completed" and r["db"] == self.label), None)
        did = self.state.get("dispute_main")
        res = {}
        if own:
            res.update({f"submission{p}": self.call("GET", f"/submissions/{own}{p}", B)[0].status_code for p in ("", "/image", "/heatmap")})
        if did:
            res["dispute"] = self.call("GET", f"/disputes/{did}", B)[0].status_code
            res["dispute (A's list as B)"] = int(did in {x["id"] for x in self.call("GET", "/disputes?limit=100", B)[1]})
        ok = res and all(v == 404 for k, v in res.items() if "list" not in k) and res.get("dispute (A's list as B)") == 0
        self.rec("TC-SEC-02", "Ownership: user B cannot read another user's data", "B opens another user's submission, image, heatmap, dispute",
                 "404 for each; not in B's dispute list", json.dumps(res), "GET as user B", "Pass" if ok else "Fail", group="SEC")
        probes = ["/submissions/..%2F..%2F.env/image", "/submissions/1%2F..%2F..%2Fapp/heatmap", "/submissions/-1/image",
                  "/submissions/99999999999999999999/image", "/submissions/1;DROP TABLE users/image", "/disputes/..%2F1"]
        res = {p: self.call("GET", p, I)[0].status_code for p in probes}
        evil = self.call("POST", "/submissions/image", I, files={"file": ("../../../evil.png", (HERE / "images" / "format_png.png").read_bytes(), "image/png")})
        stored = evil[1].get("image_submission", {}) if evil[0].status_code == 201 else {}
        ok = all(v in (404, 422) for v in res.values()) and "/" not in str(stored.get("original_filename")) and "\\" not in str(stored.get("image_path"))
        self.rec("TC-SEC-03", "Path traversal in ids and file names", "encoded ../ in ids; huge/negative ids; filename '../../../evil.png'",
                 "404/422 for ids; stored file name is a UUID, original name stripped of folders",
                 f"{json.dumps(res)}; upload {evil[0].status_code}: original_filename {stored.get('original_filename')!r}, image_path {stored.get('image_path')!r}",
                 "GET with crafted paths; POST /submissions/image", "Pass" if ok else "Fail", group="SEC")
        big = "ا" * 1_000_000
        r1 = self.call("POST", "/submissions/text", I, {"text": big})
        r2 = self.call("POST", "/disputes", I, {"submission_id": 1, "justification": "x" * 2_000_000})
        res = {"1M-char text": r1[0].status_code, "2M-char justification": r2[0].status_code}
        self.rec("TC-SEC-04", "Oversized request bodies", "1,000,000-character text; 2,000,000-character justification (images: TC-IMG-F09)",
                 "4xx, no crash", json.dumps(res), "POST", "Pass" if all(400 <= v < 500 for v in res.values()) else "Fail", group="SEC")
        origins = {"http://localhost:8082": True, "https://khabarnazar.expo.app": True, "https://khabarnazar--a1b2c3.expo.app": True,
                   "https://evil.example.com": False, "https://khabarnazar.expo.app.evil.com": False, "https://notkhabarnazar.expo.app": False}
        res = {}
        for origin, allowed in origins.items():
            r = self.http.options(self.base + API + "/submissions/text", headers={"Origin": origin, "Access-Control-Request-Method": "POST",
                                                                                   "Access-Control-Request-Headers": "authorization,content-type"})
            res[origin] = (r.status_code, r.headers.get("access-control-allow-origin"))
        ok = all((v[1] == o) == origins[o] for o, v in res.items())
        self.rec("TC-SEC-05", "CORS allows only the configured origins and regex", ", ".join(origins),
                 "Allow-Origin echoed only for localhost:8082 and *.expo.app project URLs", json.dumps(res), "OPTIONS preflight",
                 "Pass" if ok else "Fail", group="SEC")
        texts = [json.dumps(r.get("data", {}), ensure_ascii=False, default=str) for r in self.results] + [r1[1] if isinstance(r1[1], str) else json.dumps(r1[1])[:5000]]
        markers = ["Traceback", 'File "', "sqlalchemy", "psycopg", TEST_JWT_SECRET, "hashed_password", "C:\\Users"]
        hits = sorted({m for m in markers for t in texts if m in t})
        self.rec("TC-SEC-06", "No stack traces or secrets in error responses", "all recorded response data from this run", "none of: " + ", ".join(markers[:5]) + ", hashes, local paths",
                 f"found: {hits or 'none'}", "results json scan", "Pass" if not hits else "Fail", group="SEC")
        t = time.perf_counter()
        r, b, _ = self.call("GET", "/health", api=False)
        took = round(time.perf_counter() - t, 3)
        ok = r.status_code == 200 and b.get("database", {}).get("status") == "connected" and "models" in b and took < 2
        self.rec("TC-SEC-07", "/health reports the database and models quickly", "GET /health", "200; database connected; models block; < 2 s",
                 f"{r.status_code}; db {b.get('database')}; models {b.get('models')}; {took}s", "GET /health (no-load behaviour: pytest test_health_reports_model_status_without_loading_models)",
                 "Pass" if ok else "Fail", group="SEC")

    # ── TC-APP ──────────────────────────────────────────────────────────────
    def g_app(self):
        src = (BACKEND.parent / "lib" / "api.ts").read_text(encoding="utf-8")
        spec = self.call("GET", "/openapi.json", api=False)[1]
        calls = re.findall(r"request(?:Page)?<[^>]+>\(\s*[`'](/[^`'?]+)", src) + re.findall(r"apiUrl\(`(/[^`]+)`\)", src)
        norm = sorted({re.sub(r"\$\{[^}]+\}", "{id}", c) for c in calls})
        known = {re.sub(r"\{[^}]+\}", "{id}", p) for p in spec["paths"]}
        missing = [c for c in norm if API + c not in known]
        self.rec("TC-APP-01", "Every path used by lib/api.ts exists on the backend", f"{len(norm)} paths parsed from lib/api.ts", "all exist under /api/v1",
                 f"missing: {missing or 'none'}; paths {norm}", "lib/api.ts vs /openapi.json", "Pass" if not missing else "Fail", group="APP")
        iface = re.search(r"export (?:interface|type) ApiSubmission\b[^{]*\{(.*?)\n\}", src, re.S)
        fields = re.findall(r"^\s{2}(\w+)\??:", iface.group(1), re.M) if iface else []
        sample = self.call("GET", "/submissions?limit=1", self.tok("I"))[1]
        detail = self.call("GET", f"/submissions/{sample[0]['id']}", self.tok("I"))[1] if sample else {}
        admin_item = (self.call("GET", "/admin/submissions?limit=1", self.tok("admin"))[1] or [{}])[0]
        keys = set(detail) | set(sample[0] if sample else {}) | set(admin_item)
        absent = [f for f in fields if f not in keys]
        self.rec("TC-APP-02", "ApiSubmission field names match a real response", f"{len(fields)} fields of the ApiSubmission type", "every field present in the detail, list-item or admin-item response (the type covers all three)",
                 f"absent: {absent or 'none'}", "lib/api.ts type vs live response", "Pass" if fields and not absent else "Fail", group="APP")
        timeout_ms = int(re.search(r"ANALYSIS_TIMEOUT_MS = ([\d_]+)", src).group(1).replace("_", ""))
        lats = [r["data"]["latency_s"] for r in self.results if r["id"].startswith(("TC-TXT", "TC-IMG")) and r.get("data", {}).get("http_status") == 201]
        worst = max(lats) if lats else None
        self.rec("TC-APP-03", "App analysis timeout is longer than the slowest model call", f"ANALYSIS_TIMEOUT_MS = {timeout_ms}", "timeout > slowest measured check",
                 f"timeout {timeout_ms / 1000:.0f}s; slowest of {len(lats)} checks {worst}s", "lib/api.ts; TC-TXT/TC-IMG latencies",
                 "Pass" if worst and timeout_ms / 1000 > worst else "Blocked", group="APP")
        msg = "Cannot reach the backend at" in src
        self.rec("TC-APP-04", "Backend unreachable message", "fetch fails", "'Cannot reach the backend at …'", f"message in lib/api.ts: {msg}; on screen: TC-UI-19",
                 "lib/api.ts:148", "Pass" if msg else "Fail", group="APP")

    # ── TC-PERF ─────────────────────────────────────────────────────────────
    def g_perf(self):
        def stats(prefixes, cond=lambda d: True):
            v = [r["data"]["latency_s"] for r in self.results if r["db"] == self.label and r["id"].startswith(prefixes)
                 and r.get("data", {}).get("http_status") == 201 and cond(r["data"])]
            return {"n": len(v), "p50": round(statistics.median(v), 2) if v else None, "max": max(v) if v else None}
        per = {"urdu xlmr": stats("TC-TXT-", lambda d: d.get("model_version") == "xlmr-urdu"),
               "roman xlmr": stats("TC-TXT-", lambda d: d.get("model_version") == "xlmr-roman-urdu"),
               "urdu tfidf": stats("TC-TXT-", lambda d: d.get("model_version") == "tfidf-urdu-long-articles"),
               "image": stats("TC-IMG-")}
        self.state["perf_latency"] = per
        self.rec("TC-PERF-01", "Latency per route (p50 / max, seconds, first submission of each input)", "TC-TXT and TC-IMG results", "recorded (CPU)",
                 json.dumps(per), "latency_s in results", "Info", group="PERF")
        jobs = [("A", "حکومت نے آج پہلی خبر جاری کی"), ("B", "Hukoomat ne aaj doosri khabar jari ki hai ke kal chutti hogi"),
                ("A", "Hukoomat ne aaj teesri khabar di hai ke barish hogi"), ("B", "حکومت نے آج چوتھی خبر سنائی"), ("A", "حکومت نے آج پانچویں خبر دی")]
        t = time.perf_counter()
        with cf.ThreadPoolExecutor(5) as pool:
            futs = [pool.submit(lambda k, s: (k, s, self.call("POST", "/submissions/text", self.tok(k), {"text": s})), k, s) for k, s in jobs]
            outs = [f.result() for f in futs]
        wall = round(time.perf_counter() - t, 1)
        problems = []
        for key, sent, (r, b, lat) in outs:
            if r.status_code != 201:
                problems.append(f"{key}: {r.status_code}")
            elif b["text_submission"]["input_text"] != sent or b["user_id"] != self.state[key]["id"]:
                problems.append(f"{key}: mixed-up result")
        self.rec("TC-PERF-03", "Five simultaneous checks from two users", "5 parallel POST /submissions/text (3 from A, 2 from B)", "all 201; each result belongs to its sender and text",
                 f"wall {wall}s; latencies {[o[2][2] for o in outs]}; problems {problems or 'none'}", "parallel requests", "Pass" if not problems else "Fail", group="PERF")

    # ── TC-RL / lockout (server with real limits) ──────────────────────────
    def g_rl(self):
        R1, R2 = self.register("R1", "Rate One"), self.register("R2", "Rate Two")
        txt = "حکومت نے آج نئی بس سروس شروع کی"
        t = time.perf_counter()
        with cf.ThreadPoolExecutor(10) as pool:
            first = list(pool.map(lambda _: self.call("POST", "/submissions/text", R1["token"], {"text": txt}), range(10)))
        eleventh = self.call("POST", "/submissions/text", R1["token"], {"text": txt})
        elapsed = round(time.perf_counter() - t, 1)
        ok = [x[0].status_code for x in first] == [201] * 10 and eleventh[0].status_code == 429 and eleventh[0].headers.get("Retry-After")
        hist = self.call("GET", "/submissions?limit=100", R1["token"])[0].headers.get("X-Total-Count")
        self.rec("TC-RL-01", "11th check within a minute is refused; earlier ones worked", "10 parallel text checks then one more (user R1)",
                 "10x 201, then 429 with Retry-After and a clear message; history 10",
                 f"{[x[0].status_code for x in first]}; 11th {eleventh[0].status_code} Retry-After {eleventh[0].headers.get('Retry-After')} {eleventh[1].get('detail')!r}; history {hist}; {elapsed}s",
                 "POST /submissions/text", "Pass" if ok and hist == "10" else "Fail", group="RL")
        other = self.call("POST", "/submissions/text", R2["token"], {"text": txt})
        self.rec("TC-RL-02", "The limit is per user", "user R2 right after R1 was limited", "201", f"{other[0].status_code}", "POST /submissions/text",
                 "Pass" if other[0].status_code == 201 else "Fail", group="RL")
        img = (HERE / "images" / "format_png.png").read_bytes()
        ri = self.call("POST", "/submissions/image", R1["token"], files={"file": ("x.png", img, "image/png")})
        reads = [self.call("GET", p, R1["token"])[0].status_code for p in ("/submissions", "/users/me", "/disputes")]
        ok = ri[0].status_code == 429 and set(reads) == {200}
        self.rec("TC-RL-03", "Text and image checks share one counter; reads are not limited", "R1 (limited) uploads an image; reads history, profile, disputes",
                 "image 429; reads 200", f"image {ri[0].status_code}; reads {reads}", "POST /submissions/image; GETs", "Pass" if ok else "Fail", group="RL")

    def g_lockout(self):
        L = self.register("L", "Lock Me")
        st = [self.call("POST", "/auth/login", json_={"email": L["email"], "password": "bad-password"})[0].status_code for _ in range(5)]
        blocked = self.call("POST", "/auth/login", json_={"email": L["email"], "password": PASSWORD})
        print("waiting 62 s for the 1-minute lockout window…", flush=True)
        time.sleep(62)
        after = self.call("POST", "/auth/login", json_={"email": L["email"], "password": PASSWORD})[0].status_code
        ok = st == [401] * 5 and blocked[0].status_code == 429 and after == 200
        self.rec("TC-LOG-08", "Lockout after 5 failures and unlock after the window", "5 wrong logins; right password; wait 62 s; right password (server LOGIN_LOCKOUT_MINUTES=1)",
                 "5x 401; 429 even with the right password; 200 after the window",
                 f"{st}; {blocked[0].status_code} {blocked[1].get('detail')!r} Retry-After {blocked[0].headers.get('Retry-After')}; after wait {after}",
                 "POST /auth/login on the real-limits server", "Pass" if ok else "Fail", uc="UC-2 Login")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base-url", default="http://127.0.0.1:8001")
    ap.add_argument("--db", required=True)
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--label", default="sqlite")
    ap.add_argument("--groups", default="setup,reg,log,txt,img,dis,his,adm,sec,app,perf")
    ap.add_argument("--txt-ids", default="", help="comma-separated input ids for the 'txtids' group")
    args = ap.parse_args()
    runner = Runner(args)
    lite_txt = ["U01", "UL3", "R01", "E01", "X01", "X07", "X10", "X12"]
    lite_img = ["C01", "C07", "F06", "F10", "F14"]
    for g in args.groups.split(","):
        g = g.strip()
        print(f"\n=== group {g} ({args.label}) ===", flush=True)
        if g == "txtids":
            runner.g_txt(args.txt_ids.split(","))
        elif g == "txtlite":
            runner.g_txt(lite_txt)
        elif g == "imglite":
            runner.g_img(lite_img)
        else:
            getattr(runner, f"g_{g}")()
    runner.save()
    print(f"\nresults: {runner.out}")


if __name__ == "__main__":
    main()
