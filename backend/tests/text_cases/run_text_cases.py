"""Text-module test cases TC-TXT-01..34 against a running KhabarNazar backend (real models).

    python tests/text_cases/run_text_cases.py --base-url http://127.0.0.1:8001 --db sqlite:RUN/test.db
    python tests/text_cases/run_text_cases.py --only TC-TXT-04 --only TC-TXT-11
    python tests/text_cases/run_text_cases.py --only TC-TXT-34 --base-url ...   # server with the REAL rate limit

Calls the API exactly as lib/api.ts does: POST /api/v1/submissions/text {"text": ...} with a Bearer
token, GET /api/v1/submissions/{id}, GET /api/v1/submissions?skip=&limit=. Inputs come from
inputs.json next to this file, so every run uses identical text.

TC-TXT-01 and TC-TXT-31 are the only fault-injected cases. They run in a child test process
(FastAPI TestClient on the same throwaway database): TC-TXT-01 points KHABARNAZAR_URDU_XLMR_DIR at an
empty folder, TC-TXT-31 monkeypatches XLM-R inference to raise once. No model file is touched.
--db must be the throwaway database of the server under test; the real `khabarnazar` database
is refused.

Results are merged into results_<date>.json (raw responses) and results_<date>.csv
(ID, Result, Actual result / evidence). Tokens and passwords are never printed or saved.
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import statistics
import subprocess
import sys
import tempfile
import threading
import time
from datetime import date
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent
BACKEND = HERE.parents[1]
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(HERE.parent / "full_pass"))

PASSWORD = "Password123!"
TIMEOUT = 180.0          # the app's own analysis timeout (lib/api.ts ANALYSIS_TIMEOUT_MS)
RESULTS = ("Pass", "Fail", "Finding", "Known limitation", "Not run")
IDS = [f"TC-TXT-{n:02d}" for n in range(1, 40)]
INPUTS = json.loads((HERE / "inputs.json").read_text(encoding="utf-8"))


# ─── HTTP helpers ─────────────────────────────────────────────────────────────

class Api:
    def __init__(self, base: str):
        self.base = base.rstrip("/")
        self.root = self.base + "/api/v1"
        self.http = httpx.Client(timeout=TIMEOUT)

    def register_or_login(self, email: str, name: str) -> str:
        r = self.http.post(self.root + "/auth/register", json={"email": email, "password": PASSWORD, "name": name})
        if r.status_code not in (200, 201):
            r = self.http.post(self.root + "/auth/login", json={"email": email, "password": PASSWORD})
        r.raise_for_status()
        return r.json()["access_token"]

    def submit(self, token: str | None, text: str) -> dict:
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        t0 = time.perf_counter()
        r = self.http.post(self.root + "/submissions/text", json={"text": text}, headers=headers)
        latency = time.perf_counter() - t0
        try:
            body = r.json()
        except ValueError:
            body = {"_raw": r.text[:500]}
        return {"status": r.status_code, "latency_s": round(latency, 2), "body": body,
                "retry_after": r.headers.get("retry-after")}

    def get(self, token: str, sid: int) -> httpx.Response:
        return self.http.get(f"{self.root}/submissions/{sid}", headers={"Authorization": f"Bearer {token}"})

    def history(self, token: str) -> list[dict]:
        items, skip = [], 0
        while True:
            r = self.http.get(f"{self.root}/submissions?skip={skip}&limit=50", headers={"Authorization": f"Bearer {token}"})
            r.raise_for_status()
            page = r.json()
            items += page
            if len(page) < 50:
                return items
            skip += 50


def facts(resp: dict, sent: str | None = None) -> dict:
    """The evidence fields of one text check."""
    b = resp.get("body") or {}
    ts = b.get("text_submission") or {}
    ex = b.get("explainability") or {}
    words = json.loads(ex["highlighted_words"]) if ex.get("highlighted_words") else []
    f = {
        "status": resp["status"], "id": b.get("id"), "language": b.get("detected_language"),
        "model": ex.get("model_version"), "label": b.get("final_label"), "text_prediction": ts.get("text_prediction"),
        "confidence": ts.get("text_confidence"), "risk": b.get("combined_risk_score"),
        "processing_status": ts.get("processing_status"), "is_news": b.get("is_news"),
        "highlights": [w.get("word") for w in words],
        "contributions": [w.get("contribution", w.get("weight")) for w in words],
        "summary": ex.get("explanation_summary"), "latency_s": resp["latency_s"],
    }
    if sent is not None and f["highlights"]:
        from app.ai.text.preprocess import clean_urdu_notebook
        cleaned = clean_urdu_notebook(sent).casefold()
        f["highlights_not_in_input"] = [w for w in f["highlights"]
                                        if w.casefold() not in sent.casefold() and w.casefold() not in cleaned]
        f["highlights_only_after_cleaning"] = [w for w in f["highlights"]
                                               if w.casefold() not in sent.casefold() and w.casefold() in cleaned]
    return f


def ev(f: dict) -> str:
    if f["status"] not in (200, 201):
        return f"{f['status']}"
    conf = "—" if f["confidence"] is None else f"{f['confidence']:.4f}".rstrip("0").rstrip(".")
    risk = "—" if f["risk"] is None else f"{f['risk']:.4f}".rstrip("0").rstrip(".")
    return (f"{f['status']} · {f['language']} · {f['model']} · {f['label']} {conf} · risk {risk} · "
            f"{len(f['highlights'])} highlights · {f['latency_s']:.1f} s · id {f['id']}")


def is_check(f: dict, model: str, language: str | None = None) -> list[str]:
    """Problems with a normal (classified) result; empty when it meets the TC-TXT-02 expectations."""
    p = []
    if f["status"] != 201:
        p.append(f"status {f['status']}")
        return p
    if language and f["language"] != language:
        p.append(f"language {f['language']} (expected {language})")
    if f["model"] != model:
        p.append(f"model {f['model']} (expected {model})")
    if f["label"] not in ("Real", "Fake"):
        p.append(f"label {f['label']}")
    if f["confidence"] is None or not 0 <= f["confidence"] <= 1:
        p.append(f"confidence {f['confidence']}")
    if f["risk"] is None:
        p.append("no risk score")
    if not 1 <= len(f["highlights"]) <= 8:
        p.append(f"{len(f['highlights'])} highlights")
    if f.get("highlights_not_in_input"):
        p.append(f"highlights not in input: {f['highlights_not_in_input']}")
    if not f["summary"]:
        p.append("no summary")
    return p


def is_uncertain(f: dict) -> list[str]:
    p = []
    if f["status"] != 201:
        p.append(f"status {f['status']}")
    if f["label"] != "Uncertain":
        p.append(f"label {f['label']}")
    if f["confidence"] is not None or f["risk"] is not None:
        p.append(f"confidence {f['confidence']} / risk {f['risk']} (expected none)")
    return p


# ─── Fault injection (child test process) ─────────────────────────────────────

def fault_child(case: str, db: str, uploads: str) -> None:
    """Runs inside a separate test process. Prints one JSON line with the responses."""
    from fp_common import TEST_JWT_SECRET, resolve_db
    for key in [k for k in os.environ if k.startswith("KHABARNAZAR_")]:
        del os.environ[key]
    url = resolve_db(db)
    os.environ.update({"DATABASE_URL": url, "JWT_SECRET": TEST_JWT_SECRET, "PRELOAD_MODELS": "false",
                       "UPLOAD_DIR": uploads, "ENVIRONMENT": "text-cases-fault", "PYTHONUTF8": "1",
                       "CHECK_RATE_LIMIT_PER_MINUTE": "1000", "CHECK_RATE_LIMIT_PER_HOUR": "100000"})
    empty = None
    if case == "TC-TXT-01":
        empty = tempfile.mkdtemp(prefix="no-urdu-model-")
        os.environ["KHABARNAZAR_URDU_XLMR_DIR"] = empty   # an empty folder: the Urdu model is unavailable
    from fastapi.testclient import TestClient
    from app.config import settings
    assert settings.DATABASE_URL == url and url.startswith("sqlite:"), "refusing to run outside the throwaway SQLite database"
    from app.main import app
    from app.ai.text import xlmr

    logs: list[str] = []

    class Grab(logging.Handler):
        def emit(self, record):
            logs.append(f"{record.levelname} {record.name}: {record.getMessage()}"
                        + (f" [{record.exc_info[0].__name__}: {record.exc_info[1]}]" if record.exc_info else ""))

    logging.getLogger("app").addHandler(Grab())
    token = os.environ["TC_TOKEN"]
    out = {"case": case}
    with TestClient(app) as client:
        def post(text):
            t0 = time.perf_counter()
            r = client.post("/api/v1/submissions/text", json={"text": text}, headers={"Authorization": f"Bearer {token}"})
            return {"status": r.status_code, "latency_s": round(time.perf_counter() - t0, 2), "body": r.json(), "retry_after": None}

        if case == "TC-TXT-01":
            out["urdu_model_dir"] = str(xlmr.model_dir("urdu"))
            out["response"] = post(INPUTS["TC-TXT-01"])
            out["saved"] = client.get(f"/api/v1/submissions/{out['response']['body'].get('id')}",
                                      headers={"Authorization": f"Bearer {token}"}).status_code
        else:
            original = xlmr.XlmrClassifier.fake_probabilities
            calls = {"n": 0}

            def broken(self, texts, batch_size=1):
                calls["n"] += 1
                raise RuntimeError("injected inference failure (TC-TXT-31)")

            xlmr.XlmrClassifier.fake_probabilities = broken
            try:
                out["response"] = post(INPUTS["TC-TXT-31"])
            finally:
                xlmr.XlmrClassifier.fake_probabilities = original
            out["injected_calls"] = calls["n"]
            out["next"] = post(INPUTS["TC-TXT-31_next"])     # same process, real inference again
    out["logs"] = [line for line in logs if "XLM-R" in line or "inference" in line or "classifier" in line][:6]
    print("FAULT_RESULT " + json.dumps(out, ensure_ascii=False))


def run_fault(case: str, args, token: str) -> dict:
    env = {**os.environ, "TC_TOKEN": token, "PYTHONUTF8": "1"}
    uploads = str(Path(tempfile.mkdtemp(prefix="tc-fault-uploads-")))
    cmd = [sys.executable, str(Path(__file__).resolve()), "--fault-child", case, "--db", args.db, "--uploads", uploads]
    p = subprocess.run(cmd, cwd=BACKEND, env=env, capture_output=True, text=True, encoding="utf-8", timeout=900)
    line = next((l for l in p.stdout.splitlines() if l.startswith("FAULT_RESULT ")), None)
    if not line:
        raise RuntimeError(f"fault child failed ({p.returncode}): {(p.stderr or '')[-1500:]}")
    return json.loads(line[len("FAULT_RESULT "):])


# ─── The cases ────────────────────────────────────────────────────────────────

class Runner:
    def __init__(self, args):
        self.args = args
        self.api = Api(args.base_url)
        self.day = args.date
        self.json_path = HERE / f"results_{self.day}.json"
        self.data = json.loads(self.json_path.read_text(encoding="utf-8")) if self.json_path.exists() else {"meta": {}, "cases": {}}
        acc_path = HERE / f".accounts_{self.day}.json"   # emails only; password is the fixed test password
        self.accounts = json.loads(acc_path.read_text()) if acc_path.exists() else {}
        tag = int(time.time())
        for key in ("A", "B"):
            self.accounts.setdefault(key, f"txt.{key.lower()}.{tag}@example.com")
        acc_path.write_text(json.dumps(self.accounts))
        self.tokens = {k: self.api.register_or_login(v, f"Text tester {k}") for k, v in self.accounts.items()}

    # record --------------------------------------------------------------
    def rec(self, cid, result, evidence, expected, raw, notes=""):
        assert result in RESULTS, result
        self.data["cases"][cid] = {"result": result, "evidence": evidence, "expected": expected, "notes": notes,
                                   "raw": raw, "run_at": time.strftime("%Y-%m-%d %H:%M:%S"), "base_url": self.args.base_url}
        print(f"{cid:10} {result:16} {evidence}", flush=True)

    def check(self, text, user="A"):
        resp = self.api.submit(self.tokens[user], text)
        return resp, facts(resp, text)

    def prev(self, cid, key="facts"):
        c = self.data["cases"].get(cid)
        return c and c["raw"].get(key)

    def simple(self, cid, text, model, language, expected):
        resp, f = self.check(text)
        p = is_check(f, model, language)
        self.rec(cid, "Pass" if not p else "Fail", ev(f) + ("" if not p else " · " + "; ".join(p)), expected,
                 {"facts": f, "response": resp})
        return f

    # cases ---------------------------------------------------------------
    def tc01(self):
        out = run_fault("TC-TXT-01", self.args, self.tokens["A"])
        f = facts(out["response"], INPUTS["TC-TXT-01"])
        p = is_uncertain(f)
        if f["processing_status"] != "unavailable":
            p.append(f"processing_status {f['processing_status']}")
        if f["highlights"]:
            p.append("has highlights")
        if out["saved"] != 200:
            p.append(f"GET after save {out['saved']}")
        self.rec("TC-TXT-01", "Pass" if not p else "Fail",
                 ev(f) + f" · status {f['processing_status']} · model dir empty (fault-injected) · saved (GET 200)" + ("; " + "; ".join(p) if p else ""),
                 "201, saved; Uncertain; no confidence/risk; status unavailable; no highlights",
                 {"facts": f, "fault": {k: v for k, v in out.items() if k != "response"}, "response": out["response"]},
                 notes=f"Summary: {f['summary']}")

    def tc02(self):
        self.simple("TC-TXT-02", INPUTS["TC-TXT-02"], "xlmr-urdu", "urdu", "201; urdu; xlmr-urdu; Real/Fake; conf 0–1; risk; 1–8 highlights from input; summary")

    def tc03(self):
        self.simple("TC-TXT-03", INPUTS["TC-TXT-03"], "tfidf-urdu-long-articles", "urdu", "tfidf-urdu-long-articles; label; conf 0–1; 1–8 highlights from the article")

    def tc04(self):
        self.simple("TC-TXT-04", INPUTS["TC-TXT-04"], "xlmr-roman-urdu", "roman_urdu", "roman_urdu; xlmr-roman-urdu; label; conf; highlights; latency")

    def tc05(self):
        before = len(self.api.history(self.tokens["A"]))
        raw, parts, bad = {}, [], []
        for key, text in INPUTS["TC-TXT-05"].items():
            resp = self.api.submit(self.tokens["A"], text)
            detail = resp["body"].get("detail")
            msg = detail[0].get("msg") if isinstance(detail, list) and detail else detail
            raw[key] = {"status": resp["status"], "message": msg, "chars": len(text)}
            parts.append(f"{key} {resp['status']} “{msg}”")
            if resp["status"] != 422:
                bad.append(key)
        after = len(self.api.history(self.tokens["A"]))
        raw["history_before_after"] = [before, after]
        if after != before:
            bad.append(f"history grew {before}→{after}")
        self.rec("TC-TXT-05", "Pass" if not bad else "Fail", " · ".join(parts) + f" · history {before}→{after}",
                 "422 each with a clear message; none in history", raw, notes="; ".join(bad))

    def tc06(self):
        text = INPUTS["TC-TXT-06"]
        before = len(self.api.history(self.tokens["A"]))
        no_tok = self.api.submit(None, text)
        tok = self.tokens["A"]
        head, payload, sig = tok.split(".")
        tampered = ".".join([head, payload, ("A" if sig[0] != "A" else "B") + sig[1:]])
        bad_sig = self.api.submit(tampered, text)
        after = len(self.api.history(self.tokens["A"]))
        ok = no_tok["status"] == 401 and bad_sig["status"] == 401 and before == after
        self.rec("TC-TXT-06", "Pass" if ok else "Fail",
                 f"no token {no_tok['status']} “{no_tok['body'].get('detail')}” · tampered signature {bad_sig['status']} “{bad_sig['body'].get('detail')}” · history {before}→{after}",
                 "401 for both; nothing saved",
                 {"no_token": {"status": no_tok["status"], "detail": no_tok["body"].get("detail")},
                  "tampered": {"status": bad_sig["status"], "detail": bad_sig["body"].get("detail")}, "history_before_after": [before, after]})

    def tc07(self):
        self.simple("TC-TXT-07", INPUTS["TC-TXT-07"], "xlmr-urdu", "urdu", "as TC-TXT-02")

    def tc08(self):
        self.simple("TC-TXT-08", INPUTS["TC-TXT-08"], "xlmr-roman-urdu", "roman_urdu", "as TC-TXT-04")

    def tc09(self):
        from app.config import settings
        r150, f150 = self.check(INPUTS["TC-TXT-09"]["words_150"])
        r151, f151 = self.check(INPUTS["TC-TXT-09"]["words_151"])
        ok = f150["model"] == "xlmr-urdu" and f151["model"] == "tfidf-urdu-long-articles" and r150["status"] == r151["status"] == 201
        self.rec("TC-TXT-09", "Pass" if ok else "Fail",
                 f"cutoff LONG_TEXT_WORDS={settings.LONG_TEXT_WORDS} (words > cutoff → TF-IDF) · 150 words: {ev(f150)} · 151 words: {ev(f151)}",
                 "150 → xlmr-urdu; 151 → TF-IDF", {"facts_150": f150, "facts_151": f151, "response_150": r150, "response_151": r151})

    def tc10(self):
        resp, f = self.check(INPUTS["TC-TXT-10"])
        m = INPUTS["_measured"]
        truncated = "only its first part was checked" in (f["summary"] or "")
        # Highlights are not expected here: explain.py leaves them out by design when the input was truncated.
        p = [x for x in is_check(f, "xlmr-urdu", "urdu") if not x.endswith("highlights")]
        if not truncated:
            p.append("summary does not say the text was truncated")
        self.rec("TC-TXT-10", "Pass" if not p else "Fail",
                 f"{m['TC-TXT-10_words']} words, {m['TC-TXT-10_urdu_tokens']} tokens (Urdu tokenizer, limit 256) · {ev(f)} · summary says “only its first part was checked”={truncated}; no highlights for truncated text (by design, explain.py)" + ("; " + "; ".join(p) if p else ""),
                 "xlmr-urdu; no error; truncated to 256 tokens; result returned", {"facts": f, "response": resp})

    def tc11(self):
        fs, raw = [], {}
        for i, text in enumerate(INPUTS["TC-TXT-11"], 1):
            resp, f = self.check(text)
            fs.append(f)
            raw[f"variant_{i}"] = {"facts": f, "response": resp}
        routed = all(f["model"] == "xlmr-roman-urdu" and f["status"] == 201 for f in fs)
        labels = {f["label"] for f in fs}
        result = "Fail" if not routed else ("Finding" if len(labels) > 1 else "Pass")
        self.rec("TC-TXT-11", result, " | ".join(f"v{i} {f['language']} {f['model']} {f['label']} {f['confidence']} ({f['latency_s']:.1f} s, id {f['id']})"
                                                for i, f in enumerate(fs, 1)),
                 "all three xlmr-roman-urdu; labels recorded; disagreement → Finding", raw,
                 notes="Spelling variants of the same claim get different labels." if len(labels) > 1 else "")

    def tc12(self):
        pairs = [("TC-TXT-02", "TC-TXT-04"), ("TC-TXT-07", "TC-TXT-08")]
        parts, differ, missing = [], False, []
        for u, r in pairs:
            fu, fr = self.prev(u), self.prev(r)
            if not fu or not fr:
                missing.append(f"{u}/{r}")
                continue
            parts.append(f"{u} {fu['model']} {fu['label']} {fu['confidence']} vs {r} {fr['model']} {fr['label']} {fr['confidence']}")
            differ |= fu["label"] != fr["label"]
            if fu["model"] == fr["model"]:
                missing.append("same model")
        if missing:
            self.rec("TC-TXT-12", "Not run", "needs TC-TXT-02, 04, 07, 08 first: " + ", ".join(missing), "each own model; disagreement → Finding", {})
            return
        self.rec("TC-TXT-12", "Finding" if differ else "Pass", " · ".join(parts),
                 "each goes to its own model; labels disagree → Finding", {"pairs": pairs},
                 notes="The same claim in Urdu script and in Roman Urdu gets different labels from the two models." if differ else "")

    def tc13(self):
        resp, f = self.check(INPUTS["TC-TXT-13"])
        stated = "less reliable" in (f["summary"] or "")
        ok = f["status"] == 201 and f["model"] == "xlmr-roman-urdu" and stated
        self.rec("TC-TXT-13", "Known limitation" if ok else "Fail",
                 ev(f) + f" · summary says “less reliable”={stated}", "xlmr-roman-urdu; summary says no English model / less reliable",
                 {"facts": f, "response": resp}, notes="English has no model of its own (audit §15 #7).")

    def tc14(self):
        self.simple("TC-TXT-14", INPUTS["TC-TXT-14"], "xlmr-urdu", "urdu", "detected Urdu; xlmr-urdu")

    def tc15(self):
        resp, f = self.check(INPUTS["TC-TXT-15"])
        ok = f["status"] == 201 and f["model"] == "xlmr-roman-urdu"
        self.rec("TC-TXT-15", "Pass" if ok else "Fail", ev(f) + f" · detected {f['language']}", "xlmr-roman-urdu; record detected language",
                 {"facts": f, "response": resp})

    def tc16(self):
        resp, f = self.check(INPUTS["TC-TXT-16"])
        ok = f["status"] == 201
        self.rec("TC-TXT-16", "Pass" if ok else "Fail", ev(f) + f" · route {f['model']}", "record language and route; no error",
                 {"facts": f, "response": resp}, notes=f"Summary: {f['summary']}")

    def tc17(self):
        self.simple("TC-TXT-17", INPUTS["TC-TXT-17"], "xlmr-urdu", "urdu", "xlmr-urdu; no error")

    def other_script(self, cid, name):
        resp, f = self.check(INPUTS[cid])
        if f["status"] != 201:
            self.rec(cid, "Fail", ev(f), "record route; no crash", {"facts": f, "response": resp})
            return
        to_urdu = f["model"] == "xlmr-urdu"
        labelled = f["label"] in ("Real", "Fake")
        result = "Finding" if (to_urdu or labelled) else "Pass"
        note = (f"{name} text is classified by the {f['model']} model and gets a {f['label']} label." if labelled else "")
        self.rec(cid, result, ev(f), "record route; Urdu model → Finding; no crash", {"facts": f, "response": resp}, notes=note)

    def tc18(self):
        self.other_script("TC-TXT-18", "Arabic")

    def tc19(self):
        self.other_script("TC-TXT-19", "Persian")

    def tc20(self):
        self.other_script("TC-TXT-20", "Hindi (Devanagari)")

    def tc21(self):
        resp, f = self.check(INPUTS["TC-TXT-21"])
        self.rec("TC-TXT-21", "Finding" if f["status"] == 201 else "Fail", ev(f) + f" · is_news={f['is_news']}",
                 "use case: “does not appear to be news”; no news filter connected → Finding",
                 {"facts": f, "response": resp}, notes="A cooking instruction gets a news verdict: no news/not-news filter is connected (is_news is null).")

    def tc22(self):
        parts, raw, bad = [], {}, []
        for key, text in INPUTS["TC-TXT-22"].items():
            resp, f = self.check(text)
            saved = self.api.get(self.tokens["A"], f["id"]).status_code if f["id"] else None
            raw[key] = {"facts": f, "saved_get": saved, "chars": len(text)}
            parts.append(f"{key} ({len(text)} chars): {ev(f)} · GET {saved}")
            if f["status"] != 201 or saved != 200:
                bad.append(key)
        self.rec("TC-TXT-22", "Pass" if not bad else "Fail", " | ".join(parts), "both 201 and saved", raw)

    def tc23(self):
        self.uncertain_case("TC-TXT-23")

    def tc24(self):
        self.uncertain_case("TC-TXT-24")

    def uncertain_case(self, cid):
        resp, f = self.check(INPUTS[cid])
        p = is_uncertain(f)
        self.rec(cid, "Pass" if not p else "Fail", ev(f) + ("; " + "; ".join(p) if p else ""), "201; Uncertain; no confidence or risk",
                 {"facts": f, "response": resp}, notes=f"Summary: {f['summary']}")

    def tc25(self):
        resp, f = self.check(INPUTS["TC-TXT-25"])
        invented = f["confidence"] is not None or f["label"] != "Uncertain"
        result = "Fail" if f["status"] != 201 else ("Finding" if invented else "Pass")
        self.rec("TC-TXT-25", result, ev(f) + f" · summary “{(f['summary'] or '')[:90]}”", "record route; no crash; nothing invented",
                 {"facts": f, "response": resp})

    def tc26(self):
        text = INPUTS["TC-TXT-26"]
        resp, f = self.check(text)
        got = self.api.get(self.tokens["A"], f["id"]).json() if f["id"] else {}
        stored = (got.get("text_submission") or {}).get("input_text")
        same = stored == text
        old = self.data["cases"].get("TC-TXT-26", {}).get("raw", {}).get("web")
        raw = {"facts": f, "stored_equals_sent": same, "stored": stored, "response": resp}
        if old:
            raw["web"] = old
        web_ok = old.get("ok") if old else None
        result = "Fail" if f["status"] != 201 or not same or web_ok is False else ("Pass" if web_ok else "Not run")
        self.rec("TC-TXT-26", result, ev(f) + f" · stored exactly as sent={same}" + (f" · web: {old['evidence']}" if old else " · web check pending"),
                 "stored exactly; plain text on result and history; no alert", raw)

    def tc27(self):
        resp, f = self.check(INPUTS["TC-TXT-27"])
        base = self.prev("TC-TXT-04")
        if not base:
            self.rec("TC-TXT-27", "Not run", "needs TC-TXT-04 first", "same route as 04", {"facts": f})
            return
        same_route = f["model"] == base["model"]
        same_label = f["label"] == base["label"]
        result = "Fail" if f["status"] != 201 or not same_route else ("Pass" if same_label else "Finding")
        self.rec("TC-TXT-27", result,
                 ev(f) + f" · TC-TXT-04: {base['label']} {base['confidence']} · Δconf {abs((f['confidence'] or 0) - (base['confidence'] or 0)):.4f}",
                 "same route as 04; same label or record the difference", {"facts": f, "response": resp},
                 notes="Zero-width spaces change the Roman Urdu label." if not same_label else "")

    def tc28(self):
        raw, parts, same = {}, [], True
        for cid in ("TC-TXT-02", "TC-TXT-04"):
            runs = [self.check(INPUTS[cid])[1] for _ in range(2)]
            keys = [(r["label"], r["confidence"], tuple(r["highlights"])) for r in runs]
            first = self.prev(cid)
            if first:
                keys.append((first["label"], first["confidence"], tuple(first["highlights"])))
            ok = len(set(keys)) == 1
            same &= ok
            raw[cid] = {"runs": runs, "earlier": first}
            parts.append(f"{cid}×{len(keys)}: {runs[0]['label']} {runs[0]['confidence']} · highlights identical={ok} (ids {runs[0]['id']}, {runs[1]['id']})")
        self.rec("TC-TXT-28", "Pass" if same else "Fail", " | ".join(parts), "identical label, confidence and highlights", raw)

    def tc29(self):
        rows = []

        def walk(cid, node):
            if isinstance(node, dict):
                if node.get("confidence") is not None and node.get("label") in ("Real", "Fake") and node.get("id") and "risk" in node:
                    rows.append((cid, node["id"], node["label"], node["confidence"], node["risk"]))
                for value in node.values():
                    walk(cid, value)
            elif isinstance(node, list):
                for value in node:
                    walk(cid, value)

        for cid, case in self.data["cases"].items():
            if cid != "TC-TXT-29":
                walk(cid, case.get("raw"))
        rows = list({r[1]: r for r in rows}.values())
        confident = [r for r in rows if r[3] >= 0.9]
        real = [r for r in confident if r[2] == "Real"]
        fake = [r for r in confident if r[2] == "Fake"]
        bad = [r for r in real if r[4] is None or r[4] > 0.1] + [r for r in fake if r[4] is None or r[4] < 0.9]
        consistent = all(r[4] is not None and abs(r[4] - (1 - r[3] if r[2] == "Real" else r[3])) < 1e-3 for r in rows)
        top = lambda rs: ", ".join(f"{c} {lab} {conf:.4f}→risk {risk:.4f}" for c, _, lab, conf, risk in sorted(rs, key=lambda r: -r[3])[:3])
        if not rows:
            self.rec("TC-TXT-29", "Not run", "no classified results yet", "confident Real → low risk; Fake → high", {})
            return
        result = "Fail" if bad or not consistent else ("Pass" if real and fake else "Pass")
        self.rec("TC-TXT-29", result,
                 f"{len(real)} confident Real (risk ≤ {max([r[4] for r in real], default=0):.4f}): {top(real) or 'none'} · "
                 f"{len(fake)} confident Fake (risk ≥ {min([r[4] for r in fake], default=1):.4f}): {top(fake) or 'none'} · risk = P(fake) for all {len(rows)}: {consistent}",
                 "confident Real → low risk; confident Fake → high risk", {"rows": rows},
                 notes=("" if fake else "No confident Fake result occurred among these inputs, so only the Real side could be shown."))

    def tc30(self):
        parts, raw, problems, weak = [], {}, [], []
        for cid in ("TC-TXT-02", "TC-TXT-03", "TC-TXT-04"):
            f = self.prev(cid)
            if not f:
                problems.append(f"{cid} not run")
                continue
            n = len(f["highlights"])
            missing = f.get("highlights_not_in_input") or []
            if not 1 <= n <= 8 or missing or not f["summary"]:
                problems.append(f"{cid}: {n} highlights, missing {missing}, summary {bool(f['summary'])}")
            mx = max((abs(c) for c in f["contributions"] if c is not None), default=0)
            if f["confidence"] and f["confidence"] >= 0.99 and mx < 0.001:
                weak.append(f"{cid} conf {f['confidence']} max |weight| {mx:.6f}")
            raw[cid] = {"highlights": f["highlights"], "contributions": f["contributions"], "only_after_cleaning": f.get("highlights_only_after_cleaning")}
            parts.append(f"{cid}: {n} highlights, all in input={not missing}, max |weight| {mx:.4g}, summary ✓")
        result = "Fail" if problems else ("Known limitation" if weak else "Pass")
        self.rec("TC-TXT-30", result, " · ".join(parts) + (" · weak: " + "; ".join(weak) if weak else ""),
                 "1–8 highlights each in input; summary; near-zero weights at very high confidence → Known limitation", raw,
                 notes="; ".join(problems))

    def tc31(self):
        out = run_fault("TC-TXT-31", self.args, self.tokens["A"])
        f = facts(out["response"], INPUTS["TC-TXT-31"])
        n = facts(out["next"], INPUTS["TC-TXT-31_next"])
        p = is_uncertain(f)
        if not out["logs"]:
            p.append("no error logged")
        if n["status"] != 201 or n["model"] != "xlmr-urdu" or n["confidence"] is None:
            p.append(f"next request: {ev(n)}")
        self.rec("TC-TXT-31", "Pass" if not p else "Fail",
                 f"{ev(f)} · status {f['processing_status']} · log: {out['logs'][0][:110] if out['logs'] else 'none'} · next request in same process: {ev(n)}" + ("; " + "; ".join(p) if p else ""),
                 "error reported; Uncertain; no score; backend serves next request",
                 {"facts": f, "next": n, "fault": {k: v for k, v in out.items() if k not in ("response", "next")}}, notes=f"Summary: {f['summary']}")

    def tc32(self):
        token = self.tokens["A"]
        items = self.api.history(token)
        ids = [i["id"] for i in items]
        newest_first = all(items[k]["created_at"] >= items[k + 1]["created_at"] for k in range(len(items) - 1)) and ids == sorted(ids, reverse=True)
        bad_inputs = set(INPUTS["TC-TXT-05"].values())
        leaked, langs = [], 0
        for i in items:
            full = self.api.get(token, i["id"]).json()
            if (full.get("text_submission") or {}).get("input_text") in bad_inputs:
                leaked.append(i["id"])
            langs += bool(full.get("detected_language"))
        has_label = all(i.get("final_label") for i in items)
        list_has_lang = all("detected_language" in i for i in items)
        p = []
        if not newest_first:
            p.append("not newest first")
        if leaked:
            p.append(f"TC-TXT-05 inputs present: {leaked}")
        if not has_label:
            p.append("label missing")
        result = "Fail" if p else ("Pass" if list_has_lang else "Finding")
        self.rec("TC-TXT-32", result,
                 f"{len(items)} items, newest first={newest_first} (ids {ids[0]}…{ids[-1]}) · label on every item={has_label} · "
                 f"language in list response={list_has_lang} (in full record {langs}/{len(items)}) · TC-TXT-05 inputs present: {len(leaked)}",
                 "accepted checks, newest first, with label and language; no TC-TXT-05 inputs",
                 {"count": len(items), "ids": ids, "list_keys": sorted(items[0].keys()) if items else []},
                 notes="; ".join(p) or ("" if list_has_lang else "The history list response (SubmissionListItem) has no language field; the language is only in the full record."))

    def tc33(self):
        a_items = self.api.history(self.tokens["A"])
        target = a_items[0]["id"]
        r = self.api.get(self.tokens["B"], target)
        body = r.text
        a_text = (self.api.get(self.tokens["A"], target).json().get("text_submission") or {}).get("input_text") or ""
        leaked = bool(a_text) and a_text[:20] in body
        b_ids = [i["id"] for i in self.api.history(self.tokens["B"])]
        ok = r.status_code == 404 and not leaked and target not in b_ids
        self.rec("TC-TXT-33", "Pass" if ok else "Fail",
                 f"user B GET /submissions/{target} → {r.status_code} “{r.json().get('detail') if r.headers.get('content-type','').startswith('application/json') else body[:60]}” · A's text in body={leaked} · id in B's history={target in b_ids}",
                 "404; none of A's data", {"status": r.status_code, "body": body[:300]})

    def tc34(self):
        text = INPUTS["TC-TXT-34"]
        a, b = self.tokens["A"], self.tokens["B"]
        t0 = time.perf_counter()
        seq = []
        for i in range(11):
            resp = self.api.submit(a, text)
            seq.append({"n": i + 1, "status": resp["status"], "t": round(time.perf_counter() - t0, 1),
                        "detail": resp["body"].get("detail") if resp["status"] != 201 else None, "retry_after": resp["retry_after"]})
        rb = self.api.submit(b, text)
        elapsed = time.perf_counter() - t0
        statuses = [s["status"] for s in seq]
        if seq[-1]["t"] > 60:
            self.rec("TC-TXT-34", "Not run", f"11 checks took {seq[-1]['t']} s (> 60 s), so the per-minute limit could not be exercised", "", {"seq": seq})
            return
        ok = statuses[:10] == [201] * 10 and statuses[10] == 429 and rb["status"] == 201
        if statuses.count(201) == 11:
            note = "All 11 succeeded: is the server running with the real limit (CHECK_RATE_LIMIT_PER_MINUTE=10)?"
        else:
            note = ""
        self.rec("TC-TXT-34", "Pass" if ok else "Fail",
                 f"A: {statuses.count(201)}×201 then {statuses[10]} at {seq[10]['t']} s “{seq[10]['detail']}” Retry-After {seq[10]['retry_after']} · B: {rb['status']} · all within {elapsed:.0f} s",
                 "first 10 succeed; 11th 429 with clear message; B unaffected", {"seq": seq, "user_b": {"status": rb["status"]}}, notes=note)

    # run -----------------------------------------------------------------
    ORDER = [f"TC-TXT-{n:02d}" for n in (2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 1, 31, 29, 30, 32, 33)]

    def run(self, only):
        health = self.api.http.get(self.api.base + "/health").json()
        self.data["meta"].update({"date": self.day, "base_url": self.args.base_url, "server_environment": health.get("environment"),
                                  "server_database": (health.get("database") or {}).get("database"), "server_models": health.get("models")})
        assert (health.get("database") or {}).get("database") == "sqlite", "refusing: the server under test must use the throwaway SQLite database"
        todo = only or self.ORDER
        for cid in todo:
            fn = getattr(self, "tc" + cid[-2:], None)
            if fn is None:
                print(f"{cid}: not an API case (see web_text_cases.py)")
                continue
            try:
                fn()
            except Exception as exc:   # recorded, never hidden
                self.rec(cid, "Fail", f"runner error: {type(exc).__name__}: {exc}"[:300], "", {"error": repr(exc)})
            self.save()
        self.save()

    def save(self):
        save(self.json_path, self.data)


def save(json_path: Path, data: dict) -> None:
    json_path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    write_csv(json_path, data)


def write_csv(json_path: Path, data: dict) -> None:
    csv_path = json_path.with_suffix(".csv")
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(["ID", "Result", "Actual result / evidence"])
        for cid in IDS:
            c = data["cases"].get(cid)
            if c:
                w.writerow([cid, c["result"], c["evidence"] + (f" — {c['notes']}" if c.get("notes") and c["result"] in ("Finding", "Fail", "Not run") else "")])
            else:
                w.writerow([cid, "Not run", "not run yet"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://127.0.0.1:8001")
    ap.add_argument("--only", action="append", default=[], help="TC-TXT-xx (repeatable)")
    ap.add_argument("--db", default=None, help="sqlite:<path> of the server under test (needed for TC-TXT-01 and 31)")
    ap.add_argument("--date", default=date.today().isoformat())
    ap.add_argument("--fault-child", default=None, help=argparse.SUPPRESS)
    ap.add_argument("--uploads", default=None, help=argparse.SUPPRESS)
    args = ap.parse_args()
    if args.fault_child:
        fault_child(args.fault_child, args.db, args.uploads)
        return
    if any(c in args.only or not args.only for c in ("TC-TXT-01", "TC-TXT-31")) and not (args.db or "").startswith("sqlite:"):
        sys.exit("--db sqlite:<path> is required for TC-TXT-01 and TC-TXT-31")
    Runner(args).run(args.only)


if __name__ == "__main__":
    main()
