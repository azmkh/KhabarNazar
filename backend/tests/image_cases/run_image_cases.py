"""Image-module test cases TC-IMG-01..39 against a running KhabarNazar backend (real models).

    python tests/image_cases/run_image_cases.py --base-url http://127.0.0.1:8001 --run-dir RUN
    python tests/image_cases/run_image_cases.py --only TC-IMG-11 --only TC-IMG-26 --run-dir RUN
    python tests/image_cases/run_image_cases.py --only TC-IMG-39 --run-dir RUN2   # server with the REAL rate limit

RUN is the --run-dir given to tests/full_pass/start_test_server.py (throwaway SQLite RUN/test.db, uploads
RUN/uploads, uvicorn pid RUN/server.pid). Calls the API as lib/api.ts does: multipart field "file" to
POST /api/v1/submissions/image with a Bearer token; GET /api/v1/submissions/{id}, /{id}/image, /{id}/heatmap.
Inputs come from images/manifest.json (make_images.py).

Fault-injected cases (TC-IMG-01, 28, 29, 30 only) run in a child test process (FastAPI TestClient on the
same throwaway database and uploads folder) that monkeypatches OCR, the detector or the Grad-CAM backward
pass. No model or cache file is touched.

The API does not return the detector's member probabilities or the class Grad-CAM explained, so a child
"probe" process runs the same detector code (app.ai.image.ai_detector, on the EXIF-upright image exactly as
the pipeline does) over every valid asset and records P(real) per member, the ensemble label and the
explained class (probe_<date>.json). That is a read-only measurement with the real models.

Results merge into results_<date>.json (raw) and results_<date>.csv (ID, Result, Actual result / evidence).
Heatmaps are downloaded to heatmaps/. Tokens and passwords are never printed or saved.
"""
from __future__ import annotations

import argparse
import csv
import difflib
import hashlib
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
IMAGES = HERE / "images"
HEATMAPS = HERE / "heatmaps"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(HERE.parent / "full_pass"))

PASSWORD = "Password123!"
TIMEOUT = 180.0            # lib/api.ts ANALYSIS_TIMEOUT_MS; the brief asks for at least 90 s
RESULTS = ("Pass", "Fail", "Finding", "Known limitation", "Not run")
IDS = [f"TC-IMG-{n:02d}" for n in range(1, 46)]
MANIFEST = json.loads((IMAGES / "manifest.json").read_text(encoding="utf-8"))
ASSET = {}
for item in MANIFEST["images"]:
    ASSET.setdefault(item["case"], []).append(item)
MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp", ".gif": "image/gif", ".pdf": "application/pdf"}


def path_of(file: str) -> Path:
    return (IMAGES / file).resolve()


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# ─── HTTP ─────────────────────────────────────────────────────────────────────

class Api:
    def __init__(self, base: str):
        self.base = base.rstrip("/")
        self.root = self.base + "/api/v1"
        self.http = httpx.Client(timeout=TIMEOUT)

    def account(self, email: str, name: str) -> str:
        r = self.http.post(self.root + "/auth/register", json={"email": email, "password": PASSWORD, "name": name})
        if r.status_code not in (200, 201):
            r = self.http.post(self.root + "/auth/login", json={"email": email, "password": PASSWORD})
        r.raise_for_status()
        return r.json()["access_token"]

    def login(self, email: str) -> str:
        r = self.http.post(self.root + "/auth/login", json={"email": email, "password": PASSWORD})
        r.raise_for_status()
        return r.json()["access_token"]

    def upload(self, token: str | None, file: str, name: str | None = None, mime: str | None = None, timeout: float = TIMEOUT) -> dict:
        p = path_of(file)
        data = p.read_bytes()
        name = name or p.name
        mime = mime or MIME.get(Path(name).suffix.lower(), "application/octet-stream")
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        t0 = time.perf_counter()
        r = self.http.post(self.root + "/submissions/image", files={"file": (name, data, mime)}, headers=headers, timeout=timeout)
        latency = time.perf_counter() - t0
        try:
            body = r.json()
        except ValueError:
            body = {"_raw": r.text[:300]}
        return {"status": r.status_code, "latency_s": round(latency, 2), "body": body, "file": file, "sent_name": name,
                "sent_mime": mime, "sent_sha256": sha(data), "sent_bytes": len(data), "retry_after": r.headers.get("retry-after")}

    def get(self, token, path) -> httpx.Response:
        return self.http.get(self.root + path, headers={"Authorization": f"Bearer {token}"})

    def history(self, token) -> list[dict]:
        items, skip = [], 0
        while True:
            page = self.get(token, f"/submissions?skip={skip}&limit=50").json()
            items += page
            if len(page) < 50:
                return items
            skip += 50


def facts(resp: dict, probe: dict | None = None) -> dict:
    b = resp.get("body") or {}
    im = b.get("image_submission") or {}
    ex = b.get("explainability") or {}
    mv = ex.get("model_version") or ""
    f = {
        "status": resp["status"], "id": b.get("id"), "file": resp.get("file"), "latency_s": resp.get("latency_s"),
        "branch": im.get("analysis_branch"), "ocr_status": im.get("ocr_status"), "ocr_text": im.get("ocr_text"),
        "ocr_confidence": im.get("ocr_confidence"), "language": im.get("detected_language"),
        "text_model": mv.split(":", 1)[1] if mv.startswith("img-pair:") else None, "model_version": mv or None,
        "text_label": im.get("text_prediction"), "text_confidence": im.get("text_confidence"),
        "text_status": im.get("text_classification_status"),
        "image_status": im.get("image_analysis_status"), "image_score": im.get("image_score"),
        "authenticity": im.get("manipulation_prediction"), "gradcam_status": b.get("gradcam_status"),
        "heatmap_path": ex.get("heatmap_path"), "final_label": b.get("final_label"), "risk": b.get("combined_risk_score"),
        "summary": ex.get("explanation_summary"), "detail": b.get("detail"),
        "highlights": [w.get("word") for w in json.loads(ex["highlighted_words"])] if ex.get("highlighted_words") else [],
    }
    if probe:
        f["explained_class"] = probe.get("gradcam_class")
        f["p_real"] = probe.get("p_real")
        f["members"] = probe.get("members")
    return f


def short(x, n=40):
    if x is None:
        return "—"
    x = " ".join(str(x).split())
    return x if len(x) <= n else x[: n - 1] + "…"


def num(x, d=2):
    return "—" if x is None else f"{x:.{d}f}"


def ev(f: dict) -> str:
    if f["status"] not in (200, 201):
        return f"{f['status']} “{f.get('detail')}”"
    parts = [str(f["status"]), f"{f['branch']}",
             f"ocr {f['ocr_status']} {num(f['ocr_confidence'])} “{short(f['ocr_text'], 34)}”"]
    if f["text_model"]:
        parts.append(f"{f['language']} · {f['text_model']} {f['text_label']} {num(f['text_confidence'], 4)}")
    else:
        parts.append(f"lang {f['language']} · no text verdict")
    parts.append(f"image {f['image_status']} AI {num(f['image_score'], 4)} ({f['authenticity']})")
    parts.append(f"gradcam {f['gradcam_status']}" + (f" (class {f.get('explained_class')})" if f.get("explained_class") else ""))
    parts.append(f"final {f['final_label']} risk {num(f['risk'], 4)}")
    parts.append(f"{f['latency_s']:.1f} s · id {f['id']}")
    return " · ".join(parts)


# ─── child processes ──────────────────────────────────────────────────────────

def child_env(db: str, uploads: str) -> None:
    from fp_common import TEST_JWT_SECRET, resolve_db
    for key in [k for k in os.environ if k.startswith("KHABARNAZAR_")]:
        del os.environ[key]
    os.environ.update({"DATABASE_URL": resolve_db(db), "JWT_SECRET": TEST_JWT_SECRET, "PRELOAD_MODELS": "false",
                       "UPLOAD_DIR": uploads, "ENVIRONMENT": "image-cases-child", "PYTHONUTF8": "1",
                       "CHECK_RATE_LIMIT_PER_MINUTE": "1000", "CHECK_RATE_LIMIT_PER_HOUR": "100000"})


def probe_child(files: list[str]) -> None:
    """Run the real detector (as the pipeline does) on each file; print one JSON line."""
    from PIL import Image
    from app.ai.image import ai_detector
    from app.ai.image.preprocess import upright_image
    detector, reason = ai_detector.load_detector()
    if detector is None:
        print("PROBE_RESULT " + json.dumps({"error": reason}))
        return
    out = {}
    for file in files:
        try:
            with upright_image(str(path_of(file))) as up, Image.open(up) as img:
                r = detector.analyse(img)
            out[file] = {"p_real": round(r["p_real"], 4), "label": ai_detector.label_for(r["p_real"]),
                         "members": {k: round(v, 4) for k, v in r["members"].items()}, "gradcam_class": r["gradcam_class"],
                         "heatmap": r["attribution_map"] is not None, "gradcam_error": r["gradcam_error"],
                         "resnet_agrees": r["gradcam_resnet_agrees"], "sha256": sha(path_of(file).read_bytes())}
        except Exception as exc:
            out[file] = {"error": f"{type(exc).__name__}: {exc}"}
    print("PROBE_RESULT " + json.dumps(out))


def fault_child(case: str, db: str, uploads: str) -> None:
    child_env(db, uploads)
    from fastapi.testclient import TestClient
    from app.config import settings
    assert settings.DATABASE_URL.startswith("sqlite:"), "refusing to run outside the throwaway SQLite database"
    from app.main import app
    from app.ai.image import ai_detector, ocr

    logs: list[str] = []

    class Grab(logging.Handler):
        def emit(self, record):
            if record.levelno >= logging.WARNING:
                logs.append(f"{record.levelname} {record.name}: {record.getMessage()}"
                            + (f" [{record.exc_info[0].__name__}: {record.exc_info[1]}]" if record.exc_info else ""))

    logging.getLogger("app").addHandler(Grab())
    token = os.environ["IC_TOKEN"]
    file = os.environ.get("IC_FILE") or {"TC-IMG-01": "f01_64x64.png", "TC-IMG-30": "photo_landscape.jpg"}.get(case, "img02_urdu_internet.png")
    note = ""
    if case == "TC-IMG-01":
        def no_ocr():
            raise RuntimeError("injected: OCR engine unavailable (TC-IMG-01)")
        ocr.load_ocr_reader = no_ocr
        ai_detector.load_detector = lambda: (None, "the AI-image detector is unavailable (fault-injected, TC-IMG-01)")
        note = "ocr.load_ocr_reader raises; ai_detector.load_detector returns (None, reason)"
    elif case == "TC-IMG-28":
        class Broken:
            def readtext(self, *a, **k):
                raise RuntimeError("injected OCR failure (TC-IMG-28)")
        ocr.load_ocr_reader = lambda: Broken()
        note = "EasyOCR readtext raises"
    elif case == "TC-IMG-29":
        def broken_analyse(self, img):
            raise RuntimeError("injected detector failure (TC-IMG-29)")
        ai_detector.AIImageDetector.analyse = broken_analyse
        note = "real detector loaded; AIImageDetector.analyse raises"
    elif case == "TC-IMG-30":
        import torch
        def broken_backward(self, *a, **k):
            raise RuntimeError("injected Grad-CAM backward failure (TC-IMG-30)")
        torch.Tensor.backward = broken_backward
        note = "torch.Tensor.backward raises (only the Grad-CAM backward pass uses it)"
    data = path_of(file).read_bytes()
    with TestClient(app) as client:
        t0 = time.perf_counter()
        r = client.post("/api/v1/submissions/image", files={"file": (file, data, MIME[Path(file).suffix])},
                        headers={"Authorization": f"Bearer {token}"})
        resp = {"status": r.status_code, "latency_s": round(time.perf_counter() - t0, 2), "body": r.json(), "file": file,
                "sent_sha256": sha(data)}
        sid = resp["body"].get("id")
        stored = client.get(f"/api/v1/submissions/{sid}/image", headers={"Authorization": f"Bearer {token}"}) if sid else None
        heat = client.get(f"/api/v1/submissions/{sid}/heatmap", headers={"Authorization": f"Bearer {token}"}) if sid else None
    print("FAULT_RESULT " + json.dumps({"case": case, "injection": note, "response": resp,
                                         "stored_image": stored.status_code if stored is not None else None,
                                         "stored_sha_matches": stored is not None and stored.status_code == 200 and sha(stored.content) == sha(data),
                                         "heatmap_status": heat.status_code if heat is not None else None, "logs": logs[:6]},
                                        ensure_ascii=False))


def run_child(args, kind: str, payload: list[str] | str, token: str | None = None, file: str | None = None) -> dict:
    env = {**os.environ, "PYTHONUTF8": "1"}
    if file:
        env["IC_FILE"] = file
    if token:
        env["IC_TOKEN"] = token
    cmd = [sys.executable, str(Path(__file__).resolve()), f"--{kind}-child", json.dumps(payload),
           "--run-dir", args.run_dir]
    p = subprocess.run(cmd, cwd=BACKEND, env=env, capture_output=True, text=True, encoding="utf-8", timeout=1800)
    marker = "PROBE_RESULT " if kind == "probe" else "FAULT_RESULT "
    line = next((l for l in p.stdout.splitlines() if l.startswith(marker)), None)
    if not line:
        raise RuntimeError(f"{kind} child failed ({p.returncode}): {(p.stderr or '')[-1500:]}")
    return json.loads(line[len(marker):])


def ps_memory(pid: str) -> dict:
    """Working set of the uvicorn interpreter. The venv python.exe is a launcher that starts the real
    interpreter as a child process, so the largest process among pid and its children is measured."""
    cmd = (f"$ids = @({pid}) + @(Get-CimInstance Win32_Process -Filter 'ParentProcessId={pid}' | ForEach-Object ProcessId); "
           "$p = Get-Process -Id $ids | Sort-Object WorkingSet64 -Descending | Select-Object -First 1; "
           "'{0} {1}' -f $p.WorkingSet64, $p.PeakWorkingSet64")
    out = subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True).stdout.split()
    return {"working_set_mb": round(int(out[0]) / 2**20), "peak_working_set_mb": round(int(out[1]) / 2**20)} if len(out) == 2 else {}


# ─── the cases ────────────────────────────────────────────────────────────────

class Runner:
    def __init__(self, args):
        self.args = args
        self.run = Path(args.run_dir).resolve()
        self.uploads = self.run / "uploads"
        self.api = Api(args.base_url)
        self.json_path = HERE / f"results_{args.date}.json"
        self.data = json.loads(self.json_path.read_text(encoding="utf-8")) if self.json_path.exists() else {"meta": {}, "cases": {}}
        acc = HERE / f".accounts_{args.date}.json"
        self.emails = json.loads(acc.read_text()) if acc.exists() else {}
        tag = int(time.time())
        for k in ("A", "B", "ADMIN"):
            self.emails.setdefault(k, f"img.{k.lower()}.{tag}@example.com")
        acc.write_text(json.dumps(self.emails))
        self.tok = {k: self.api.account(v, f"Image tester {k}") for k, v in self.emails.items()}
        self.make_admin()
        probe_path = HERE / f"probe_{args.date}.json"
        self.probe = json.loads(probe_path.read_text(encoding="utf-8")) if probe_path.exists() else {}
        self.probe_path = probe_path

    def make_admin(self):
        from fp_common import TEST_JWT_SECRET, resolve_db
        env = {k: v for k, v in os.environ.items() if not k.startswith("KHABARNAZAR_")}
        env.update({"DATABASE_URL": resolve_db(f"sqlite:{self.run / 'test.db'}"), "JWT_SECRET": TEST_JWT_SECRET, "PYTHONUTF8": "1"})
        subprocess.run([sys.executable, "scripts/set_user_role.py", self.emails["ADMIN"], "admin"], cwd=BACKEND, env=env,
                       check=True, capture_output=True)

    def ensure_probe(self):
        files = [i["file"] for i in MANIFEST["images"]
                 if Path(i["file"]).suffix.lower() in (".png", ".jpg", ".webp") and not i["file"].startswith(("f04", "f20", "f21", "f22", "f23", "f24"))
                 and "../" not in i["file"]]
        files.append("../../fixtures/urdu_headline.png")
        missing = [f for f in files if f not in self.probe]
        if missing:
            print(f"probing {len(missing)} assets with the real detector…", flush=True)
            self.probe.update(run_child(self.args, "probe", missing))
            self.probe_path.write_text(json.dumps(self.probe, indent=1), encoding="utf-8")

    def upload_count(self):
        return sum(1 for p in self.uploads.iterdir() if p.is_file()) if self.uploads.exists() else None

    # record ----------------------------------------------------------------
    def rec(self, cid, result, evidence, expected, raw, notes=""):
        assert result in RESULTS, result
        self.data["cases"][cid] = {"result": result, "evidence": evidence, "expected": expected, "notes": notes, "raw": raw,
                                   "run_at": time.strftime("%Y-%m-%d %H:%M:%S"), "base_url": self.args.base_url}
        print(f"{cid:10} {result:16} {evidence}", flush=True)

    def check(self, file, user="A", **kw):
        resp = self.api.upload(self.tok[user], file, **kw)
        f = facts(resp, self.probe.get(file))
        f["user"] = user
        if f["status"] == 201 and f["heatmap_path"]:
            r = self.api.get(self.tok[user], f"/submissions/{f['id']}/heatmap")
            if r.status_code == 200:
                HEATMAPS.mkdir(exist_ok=True)
                hp = HEATMAPS / f"{Path(file).stem}_id{f['id']}.png"
                hp.write_bytes(r.content)
                from PIL import Image
                with Image.open(hp) as h:
                    f["heatmap_size"] = list(h.size)
                f["heatmap_file"] = f"backend/tests/image_cases/heatmaps/{hp.name}"
                f["heatmap_sha256"] = sha(r.content)
        return resp, f

    def prev(self, cid, key="facts"):
        c = self.data["cases"].get(cid)
        return c and c["raw"].get(key)

    def processed(self, cid, file, expected, need_heatmap=False, extra_check=None):
        resp, f = self.check(file)
        p = []
        if f["status"] != 201:
            p.append(f"status {f['status']}")
        elif f["image_status"] != "completed":
            p.append(f"image analysis {f['image_status']}")
        if need_heatmap and f["status"] == 201 and f["gradcam_status"] != "completed":
            p.append(f"gradcam {f['gradcam_status']}")
        if extra_check:
            p += extra_check(f)
        self.rec(cid, "Pass" if not p else "Fail", ev(f) + ("; " + "; ".join(p) if p else ""), expected, {"facts": f, "response": resp})
        return f

    def known_ai(self, f):
        return f["image_score"] is not None and f["image_score"] >= 0.5

    def text_case(self, cid, file, model, language, expected, note_check=None, ai_known=False):
        resp, f = self.check(file)
        p = []
        if f["status"] != 201:
            p.append(f"status {f['status']}")
        else:
            if f["branch"] != "image_pair":
                p.append(f"branch {f['branch']} (OCR {f['ocr_status']} {f['ocr_confidence']})")
            if language and f["language"] != language:
                p.append(f"language {f['language']} (expected {language})")
            if model and f["text_model"] != model:
                p.append(f"text model {f['text_model']} (expected {model})")
            if f["image_score"] is None:
                p.append("no image_score")
            if f["gradcam_status"] != "completed":
                p.append(f"gradcam {f['gradcam_status']}")
            if note_check:
                p += note_check(f)
        result = "Fail" if p else ("Known limitation" if ai_known and self.known_ai(f) else "Pass")
        notes = ("High AI-generated score on rendered text (audit Finalization: screenshots/rendered text rated AI-generated); "
                 "presentation checked separately.") if result == "Known limitation" else ""
        self.rec(cid, result, ev(f) + ("; " + "; ".join(p) if p else ""), expected, {"facts": f, "response": resp}, notes=notes)
        return f

    def rejected(self, cid, items, expected, codes=(400, 413, 415)):
        before_h, before_u = len(self.api.history(self.tok["A"])), self.upload_count()
        parts, raw, bad = [], {}, []
        for label, file, kw in items:
            resp = self.api.upload(self.tok["A"], file, **kw)
            raw[label] = {"status": resp["status"], "detail": resp["body"].get("detail"), "latency_s": resp["latency_s"], "bytes": resp["sent_bytes"]}
            parts.append(f"{label} → {resp['status']} “{resp['body'].get('detail')}”")
            if resp["status"] not in codes:
                bad.append(label)
        after_h, after_u = len(self.api.history(self.tok["A"])), self.upload_count()
        raw["history"], raw["upload_files"] = [before_h, after_h], [before_u, after_u]
        if after_h != before_h or after_u != before_u:
            bad.append(f"saved: history {before_h}→{after_h}, upload files {before_u}→{after_u}")
        self.rec(cid, "Pass" if not bad else "Fail", " · ".join(parts) + f" · history {before_h}→{after_h}, upload files {before_u}→{after_u}",
                 expected, raw, notes="; ".join(bad))
        return raw

    def fault(self, cid, file=None):
        out = run_child(self.args, "fault", cid, self.tok["A"], file=file)
        return out, facts(out["response"])

    # cases ----------------------------------------------------------------
    def tc01(self):
        out, f = self.fault("TC-IMG-01")
        p = []
        if f["status"] != 201: p.append(f"status {f['status']}")
        if not out["stored_sha_matches"]: p.append("file not stored")
        if f["final_label"] != "Uncertain": p.append(f"final {f['final_label']}")
        if f["image_status"] != "unavailable": p.append(f"image analysis {f['image_status']}")
        if f["image_score"] is not None or f["risk"] is not None: p.append("score invented")
        if f["heatmap_path"] or out["heatmap_status"] == 200: p.append("heatmap invented")
        self.rec("TC-IMG-01", "Pass" if not p else "Fail",
                 ev(f) + f" · stored file served, SHA-256 matches={out['stored_sha_matches']} · heatmap GET {out['heatmap_status']}" + ("; " + "; ".join(p) if p else ""),
                 "201; stored; final Uncertain; image check unavailable; nothing invented",
                 {"facts": f, "fault": {k: v for k, v in out.items() if k != "response"}}, notes=f"Injected: {out['injection']}. Summary: {f['summary']}")

    def control(self, cid, file):
        """Same text in Segoe UI (Naskh-style): shows whether a low OCR score comes from the Nastaliq font."""
        resp, f = self.check(file)
        c = self.data["cases"][cid]
        c["raw"]["control"] = f
        c["evidence"] += (f" · control, same text in Segoe UI: OCR {f['ocr_status']} {num(f['ocr_confidence'])}, {f['branch']}, "
                          f"{f['text_model'] or 'no text verdict'} {f['text_label'] or ''} (id {f['id']})")

    def tc02(self):
        f = self.text_case("TC-IMG-02", "img02_urdu_internet.png", "xlmr-urdu", "urdu", "OCR reads it; Urdu; xlmr-urdu verdict; image_score; heatmap")
        self.control("TC-IMG-02", "ctl02_urdu_segoe.png")
        if self.data["cases"]["TC-IMG-02"]["result"] == "Fail" and f["branch"] == "ai_or_real":
            self.data["cases"]["TC-IMG-02"]["notes"] = (f"EasyOCR read the Nastaliq-rendered text at {num(f['ocr_confidence'])}, below the 0.3 cutoff, "
                                                        "so no text verdict was produced. See the Segoe UI control in the evidence.")

    def tc03(self):
        def chk(f):
            p = []
            if f["ocr_status"] != "no_text_found": p.append(f"ocr_status {f['ocr_status']} “{short(f['ocr_text'])}”")
            if f["final_label"] != "Uncertain": p.append(f"final {f['final_label']}")
            if f["risk"] is not None: p.append(f"risk {f['risk']}")
            return p
        resp, f = self.check("photo_landscape.jpg")
        p = chk(f) if f["status"] == 201 else [f"status {f['status']}"]
        if f["image_score"] is None: p.append("no image_score")
        if f["gradcam_status"] not in ("completed", "unavailable"): p.append(f"gradcam {f['gradcam_status']}")
        self.rec("TC-IMG-03", "Pass" if not p else "Fail", ev(f) + ("; " + "; ".join(p) if p else ""),
                 "no_text_found; final Uncertain; risk None; image_score; Grad-CAM attempted", {"facts": f, "response": resp})

    def tc04(self):
        self.rejected("TC-IMG-04", [(".txt renamed .png", "f04_text_renamed.png", {}), ("PDF", "f04_document.pdf", {})],
                      "rejected 400/415 with a clear message; nothing saved", codes=(400, 415))

    def tc05(self):
        before = len(self.api.history(self.tok["A"])), self.upload_count()
        r1 = self.api.upload(None, "img02_urdu_internet.png")
        head, payload, sig = self.tok["A"].split(".")
        r2 = self.api.upload(".".join([head, payload, ("A" if sig[0] != "A" else "B") + sig[1:]]), "img02_urdu_internet.png")
        after = len(self.api.history(self.tok["A"])), self.upload_count()
        ok = r1["status"] == r2["status"] == 401 and before == after
        self.rec("TC-IMG-05", "Pass" if ok else "Fail",
                 f"no token {r1['status']} “{r1['body'].get('detail')}” · tampered {r2['status']} “{r2['body'].get('detail')}” · history/upload files {before}→{after}",
                 "401 for both; nothing saved", {"no_token": r1["status"], "tampered": r2["status"], "before_after": [before, after]})

    def tc06(self):
        f = self.text_case("TC-IMG-06", "../../fixtures/urdu_headline.png", None, None,
                           "OCR text; text verdict; detector score; heatmap; compare OCR 0.44, Real, AI 0.94", ai_known=True)
        c = self.data["cases"]["TC-IMG-06"]
        c["evidence"] += f" · report: OCR 0.44, Real, AI 0.94 → now OCR {num(f['ocr_confidence'])}, {f['text_label']}, AI {num(f['image_score'])}"

    def tc07(self):
        self.text_case("TC-IMG-07", "img07_roman_internet.png", "xlmr-roman-urdu", "roman_urdu", "Roman Urdu; xlmr-roman-urdu; image_score; heatmap")

    def tc08(self):
        def note(f):
            return [] if "less reliable" in (f["summary"] or "") else ["no lower-reliability note in the summary"]
        f = self.text_case("TC-IMG-08", "img08_english_textbooks.png", "xlmr-roman-urdu", None,
                           "xlmr-roman-urdu with the lower-reliability note; image_score; heatmap", note_check=note)
        c = self.data["cases"]["TC-IMG-08"]
        only_note = (c["result"] == "Fail" and f["text_model"] == "xlmr-roman-urdu" and f["language"] == "mixed"
                     and c["evidence"].endswith("no lower-reliability note in the summary"))
        if only_note:
            c["result"] = "Finding"
            c["notes"] = ("Routed to xlmr-roman-urdu as expected, but OCR inserted an Arabic-script letter, so the text was detected as "
                          "'mixed' and the summary carries the mixed-script note instead of the English lower-reliability note.")
        elif c["result"] != "Fail":
            c["result"] = "Known limitation"
            c["notes"] = "English goes through the Roman Urdu model (audit Finalization); the summary says it is less reliable." + \
                         (" High AI score on rendered text is also a known limitation." if self.known_ai(f) else "")

    def tc09(self):
        resp, f = self.check("img09_mixed_petrol.png")
        ok = f["status"] == 201
        self.rec("TC-IMG-09", "Pass" if ok else "Fail", ev(f) + f" · OCR text “{short(f['ocr_text'], 80)}”",
                 "record OCR text, language and route; no error", {"facts": f, "response": resp})

    def tc10(self):
        resp, f = self.check("img10_urdu_paragraph.png")
        src = next(i for i in MANIFEST["images"] if i["file"] == "img10_urdu_paragraph.png")["text"].split("\n")
        lines = [l for l in (f["ocr_text"] or "").split("\n") if l.strip()]
        idx = [max(range(len(src)), key=lambda k: difflib.SequenceMatcher(None, l, src[k]).ratio()) for l in lines]
        in_order = idx == sorted(idx)
        p = []
        if f["status"] != 201: p.append(f"status {f['status']}")
        if not lines: p.append("no OCR text")
        if f["branch"] != "image_pair": p.append(f"no text verdict ({f['branch']})")
        result = "Fail" if p else ("Pass" if in_order else "Finding")
        self.rec("TC-IMG-10", result,
                 ev(f) + f" · {len(lines)} OCR lines map to source lines {[i + 1 for i in idx]} (reading order={in_order})" + ("; " + "; ".join(p) if p else ""),
                 "OCR text in reading order; text verdict", {"facts": f, "line_map": idx, "ocr_lines": lines, "response": resp},
                 notes=("" if in_order else "OCR returned the paragraph lines out of reading order. ")
                 + ("" if f["branch"] == "image_pair" else f"OCR confidence {num(f['ocr_confidence'])} is below the 0.3 cutoff, so no verdict."))
        self.control("TC-IMG-10", "ctl10_paragraph_segoe.png")
        ctl = self.data["cases"]["TC-IMG-10"]["raw"]["control"]
        ctl_lines = [l for l in (ctl["ocr_text"] or "").split("\n") if l.strip()]
        ctl_idx = [max(range(len(src)), key=lambda k: difflib.SequenceMatcher(None, l, src[k]).ratio()) for l in ctl_lines]
        self.data["cases"]["TC-IMG-10"]["evidence"] += f"; control lines map to {[i + 1 for i in ctl_idx]} (in order={ctl_idx == sorted(ctl_idx)})"

    def tc11(self):
        parts, raw, p, below = [], {}, [], []
        for label, file in (("blurred", "img11a_blurred.png"), ("light grey", "img11b_light_grey.png")):
            resp, f = self.check(file)
            raw[label] = {"facts": f, "response": resp}
            conf = f["ocr_confidence"]
            skipped = f["branch"] == "ai_or_real"
            under = conf is None or conf < 0.3
            below.append(under)
            reason = "OCR found only a little or unclear text" in (f["summary"] or "") or "no readable text" in (f["summary"] or "")
            parts.append(f"{label}: ocr {f['ocr_status']} conf {num(conf)} → text check {'skipped' if skipped else 'run'}"
                         + (f" (reason in summary={reason})" if skipped else f" ({f['text_model']} {f['text_label']})")
                         + f", image {f['image_status']} AI {num(f['image_score'])}, gradcam {f['gradcam_status']}, id {f['id']}")
            if f["status"] != 201 or f["image_status"] != "completed" or f["gradcam_status"] != "completed":
                p.append(f"{label}: image/heatmap did not run")
            if under and (not skipped or not reason):
                p.append(f"{label}: under cutoff but text was checked or no reason")
            if not under and skipped and sum(c.isalpha() for c in (f['ocr_text'] or '')) >= 10:
                p.append(f"{label}: above cutoff with enough letters but skipped")
        result = "Fail" if p else ("Pass" if all(below) else "Finding")
        self.rec("TC-IMG-11", result, " | ".join(parts) + ("; " + "; ".join(p) if p else ""),
                 "below 0.3: text check skipped with a reason; image analysis + heatmap still run; record confidences", raw,
                 notes="" if all(below) else "At least one degraded image was still read above the 0.3 cutoff, so its text was classified; the below-cutoff path was exercised only where noted.")

    def tc12(self):
        self.text_case("TC-IMG-12", "img12_photo_caption.jpg", None, None, "OCR reads the caption; text verdict; image_score; heatmap")

    def tc13(self):
        old_web = ((self.data["cases"].get("TC-IMG-13") or {}).get("raw") or {}).get("web")
        self.text_case("TC-IMG-13", "img13_news_card.png", None, None, "text verdict + separate authenticity result (API); screen check separate", ai_known=True)
        c = self.data["cases"]["TC-IMG-13"]
        c["raw"]["web"] = old_web
        if old_web:
            c["evidence"] += " · screen: " + old_web["evidence"]
            if not old_web.get("ok"):
                c["result"] = "Fail"
        else:
            c["evidence"] += " · screen check pending (web_image_cases.py)"

    def tc14(self):
        resp, f = self.check("photo_ai_look.png")
        p = []
        if f["status"] != 201: p.append(f"status {f['status']}")
        if f["image_score"] is None: p.append("no image_score")
        if f["final_label"] != "Uncertain": p.append(f"final {f['final_label']}")
        if f["gradcam_status"] != "completed": p.append(f"gradcam {f['gradcam_status']}")
        self.rec("TC-IMG-14", "Pass" if not p else ("Known limitation" if p == [f"gradcam {f['gradcam_status']}"] and "leaned strongly the other way" in (f["summary"] or "") else "Fail"),
                 ev(f) + ("; " + "; ".join(p) if p else ""), "image_score and label; final Uncertain; heatmap", {"facts": f, "response": resp})

    def tc15(self):
        self.text_case("TC-IMG-15", "img15_meme_roman.jpg", None, None, "OCR text verdict and image_score; heatmap")

    def tc16(self):
        self.processed("TC-IMG-16", "f16_valid.jpg", "201; processed")

    def tc17(self):
        self.processed("TC-IMG-17", "f17_valid.webp", "201; processed")

    def tc18(self):
        self.processed("TC-IMG-18", "f18_alpha.png", "201; no crash; heatmap", need_heatmap=True)

    def tc19(self):
        self.processed("TC-IMG-19", "f19_greyscale.jpg", "201; no crash; heatmap", need_heatmap=True)

    def tc20(self):
        resp, f = self.check("f20_1x1.png")
        ok = f["status"] == 201 or (400 <= f["status"] < 500 and f.get("detail"))
        invented = f["status"] == 201 and (f["ocr_text"] or f["final_label"] != "Uncertain")
        scored = f["status"] == 201 and f["image_score"] is not None
        self.rec("TC-IMG-20", "Fail" if not ok or invented else ("Finding" if scored else "Pass"),
                 ev(f) + (" · the 1×1 picture is upscaled to 224×224 and still gets an AI-generated score, label and heatmap" if scored else ""),
                 "processed or clear error; no crash; nothing invented", {"facts": f, "response": resp},
                 notes="No news verdict is invented (final Uncertain), but the detector returns a label and a heatmap for a single pixel; a minimum-size check would be clearer." if scored else "")

    def tc21(self):
        pid = (self.run / "server.pid").read_text().strip() if (self.run / "server.pid").exists() else None
        before = ps_memory(pid) if pid else {}
        r1, f1 = self.check("f21_8000x8000.png")
        mid = ps_memory(pid) if pid else {}
        r2, f2 = self.check("f21b_6000x6000.png")
        after = ps_memory(pid) if pid else {}
        ok = (f1["status"] == 201 or (f1["status"] in (400, 413, 415) and f1.get("detail"))) and f2["status"] in (201, 413)
        self.rec("TC-IMG-21", "Pass" if ok else "Fail",
                 f"8000×8000 ({r1['sent_bytes'] // 1024} KB): {ev(f1)} in {f1['latency_s']:.1f} s · extra 6000×6000: {ev(f2)} · server RAM {before.get('working_set_mb')}→{after.get('working_set_mb')} MB, peak {after.get('peak_working_set_mb')} MB",
                 "processed or clear error; no crash; record time and peak RAM", {"facts_8000": f1, "facts_6000": f2, "memory": [before, mid, after]})

    def tc22(self):
        resp, f = self.check("f22a_just_under_10mb.png")
        raw = self.rejected("TC-IMG-22x", [("just over 10 MB", "f22b_just_over_10mb.png", {})], "", codes=(413,))
        self.data["cases"].pop("TC-IMG-22x", None)
        over = raw["just over 10 MB"]
        ok = f["status"] == 201 and over["status"] == 413 and raw["history"][0] == raw["history"][1]
        self.rec("TC-IMG-22", "Pass" if ok else "Fail",
                 f"under ({resp['sent_bytes']} B): {ev(f)} · over ({over['bytes']} B): {over['status']} “{over['detail']}” · nothing saved={raw['history'][0] == raw['history'][1] and raw['upload_files'][0] == raw['upload_files'][1]}",
                 "under: 201; over: 413 clear message, nothing saved", {"under": f, "over": raw})

    def tc23(self):
        self.rejected("TC-IMG-23", [("GIF", "f23.gif", {})], "rejected with a clear message; nothing saved")

    def tc24(self):
        raw = self.rejected("TC-IMG-24", [("truncated JPEG", "f24_truncated.jpg", {})], "rejected; nothing saved; next request served")
        resp, f = self.check("f16_valid.jpg")
        c = self.data["cases"]["TC-IMG-24"]
        c["raw"]["next"] = f
        c["evidence"] += f" · next request: {f['status']} id {f['id']}"
        if f["status"] != 201:
            c["result"] = "Fail"

    def tc25(self):
        resp, f = self.check("f25_png_named.jpg", mime="image/jpeg")
        ok = f["status"] == 201
        stored = self.api.get(self.tok["A"], f"/submissions/{f['id']}").json().get("image_submission", {}) if ok else {}
        self.rec("TC-IMG-25", "Pass" if ok and stored.get("mime_type") == "image/png" else "Fail",
                 ev(f) + f" · sent as image/jpeg named .jpg → stored mime {stored.get('mime_type')}, path {stored.get('image_path')}",
                 "handled by its real content; 201", {"facts": f, "stored": {k: stored.get(k) for k in ("mime_type", "image_path", "original_filename")}})

    def tc26(self):
        resp, f = self.check("f26_exif6.jpg")
        meta = next(i for i in MANIFEST["images"] if i["file"] == "f26_exif6.jpg")
        p = []
        if f["status"] != 201: p.append(f"status {f['status']}")
        if f.get("heatmap_size") != meta["upright_size"]: p.append(f"heatmap size {f.get('heatmap_size')} (expected {meta['upright_size']})")
        read_upright = f["branch"] == "image_pair"
        self.rec("TC-IMG-26", "Pass" if not p and read_upright else ("Fail" if p else "Finding"),
                 ev(f) + f" · stored 900×600 + EXIF 6 → heatmap {f.get('heatmap_size')} (upright 600×900) · OCR read the upright text={read_upright} · {f.get('heatmap_file')}",
                 "analysed upright; heatmap 600×900 lines up", {"facts": f, "response": resp})

    def tc27(self):
        resp, f = self.check("img02_urdu_internet.png")
        r = self.api.get(self.tok["A"], f"/submissions/{f['id']}/image")
        same = r.status_code == 200 and sha(r.content) == resp["sent_sha256"]
        self.rec("TC-IMG-27", "Pass" if same else "Fail",
                 f"upload SHA-256 {resp['sent_sha256'][:16]}… · download {r.status_code} SHA-256 {sha(r.content)[:16]}… · equal={same} · id {f['id']}",
                 "download SHA-256 equals upload", {"upload": resp["sent_sha256"], "download": sha(r.content), "status": r.status_code, "id": f["id"], "facts": f})

    def tc28(self):
        out, f = self.fault("TC-IMG-28")
        p = []
        if f["status"] != 201: p.append(f"status {f['status']}")
        if f["ocr_status"] == "no_text_found": p.append("ocr_status no_text_found")
        if f["image_status"] != "completed" or f["gradcam_status"] != "completed": p.append(f"image {f['image_status']}, gradcam {f['gradcam_status']}")
        self.rec("TC-IMG-28", "Pass" if not p else "Fail",
                 ev(f) + f" · ocr_status “{f['ocr_status']}” (the code's value for a failed OCR; there is no “failed” value) · log: {short(out['logs'][0] if out['logs'] else 'none', 90)}" + ("; " + "; ".join(p) if p else ""),
                 "ocr_status failed (not no_text_found); image analysis and heatmap run",
                 {"facts": f, "fault": {k: v for k, v in out.items() if k != "response"}}, notes=f"Injected: {out['injection']}. Summary: {short(f['summary'], 200)}")

    def substitute_for_02(self):
        """TC-IMG-02's own image when it produced a text verdict; otherwise the repo fixture (TC-IMG-06), which does."""
        a = self.prev("TC-IMG-02")
        if a and a["branch"] == "image_pair":
            return None, "img02_urdu_internet.png"
        return "../../fixtures/urdu_headline.png", "../../fixtures/urdu_headline.png"

    def tc29(self):
        sub, used = self.substitute_for_02()
        out, f = self.fault("TC-IMG-29", file=sub)
        p = []
        if f["status"] != 201: p.append(f"status {f['status']}")
        if f["image_status"] != "unavailable" or f["image_score"] is not None: p.append(f"image {f['image_status']} score {f['image_score']}")
        if f["branch"] != "image_pair" or f["text_label"] not in ("Real", "Fake"): p.append(f"OCR verdict lost ({f['branch']}, {f['text_label']})")
        if f["heatmap_path"]: p.append("heatmap invented")
        self.rec("TC-IMG-29", "Pass" if not p else "Fail",
                 f"image {used}" + (" (substitute: TC-IMG-02 gave no text verdict)" if sub else "") + " · " + ev(f)
                 + f" · log: {short(out['logs'][0] if out['logs'] else 'none', 90)}" + ("; " + "; ".join(p) if p else ""),
                 "image analysis failed; no score invented; OCR text verdict kept",
                 {"facts": f, "fault": {k: v for k, v in out.items() if k != "response"}}, notes=f"Injected: {out['injection']}. Summary: {short(f['summary'], 220)}")

    def tc30(self):
        out, f = self.fault("TC-IMG-30")
        p = []
        if f["status"] != 201: p.append(f"status {f['status']}")
        if f["gradcam_status"] != "unavailable" or f["heatmap_path"] or out["heatmap_status"] == 200: p.append(f"gradcam {f['gradcam_status']}, heatmap {f['heatmap_path']}")
        if f["image_status"] != "completed" or f["image_score"] is None: p.append("image prediction lost")
        reported = "Grad-CAM heatmap unavailable" in (f["summary"] or "")
        if not reported: p.append("not reported in the summary")
        self.rec("TC-IMG-30", "Pass" if not p else "Fail",
                 ev(f) + f" · summary: “{short((f['summary'] or '').split('Grad-CAM heatmap unavailable')[-1], 70)}” · heatmap GET {out['heatmap_status']}" + ("; " + "; ".join(p) if p else ""),
                 "explanation unavailable; no heatmap invented; prediction kept",
                 {"facts": f, "fault": {k: v for k, v in out.items() if k != "response"}}, notes=f"Injected: {out['injection']}.")

    def tc31(self):
        a, b = self.prev("TC-IMG-02"), self.prev("TC-IMG-03")
        if not a or not b:
            return self.rec("TC-IMG-31", "Not run", "needs TC-IMG-02 and 03", "", {})
        ok = a["gradcam_status"] == b["gradcam_status"] == "completed"
        self.rec("TC-IMG-31", "Pass" if ok else "Fail",
                 f"02 ({a['branch']}, OCR {a['ocr_status']} {num(a['ocr_confidence'])}): gradcam {a['gradcam_status']} · 03 ({b['branch']}, OCR {b['ocr_status']}): gradcam {b['gradcam_status']} — OCR and Grad-CAM both ran on each",
                 "gradcam completed for both", {"02": a["gradcam_status"], "03": b["gradcam_status"]})

    def disagreeing(self):
        rows = [(f, v) for f, v in self.probe.items() if isinstance(v, dict) and "p_real" in v and not v["resnet_agrees"]]
        return sorted(rows, key=lambda r: abs(r[1]["members"]["resnet18_robust"] - 0.5), reverse=True)

    def submit_probe(self, file):
        for c in self.data["cases"].values():
            for v in (c.get("raw") or {}).values():
                if isinstance(v, dict) and v.get("file") == file and v.get("status") == 201:
                    return v
        return self.check(file)[1]

    def tc32(self):
        rows = [r for r in self.disagreeing() if r[1]["heatmap"]]
        if not rows:
            return self.rec("TC-IMG-32", "Not run",
                            f"no asset where ResNet18 disagrees with the ensemble AND a heatmap is produced (searched {len(self.probe)} assets)", "", {"probe": self.probe})
        file, pr = rows[0]
        f = self.submit_probe(file)
        label_class = "real" if pr["p_real"] >= 0.5 else "fake"
        ok = pr["gradcam_class"] == label_class and f["gradcam_status"] == "completed"
        self.rec("TC-IMG-32", "Pass" if ok else "Fail",
                 f"{file}: ensemble P(real) {pr['p_real']:.4f} → {pr['label']} · ResNet18 P(real) {pr['members']['resnet18_robust']:.4f} (disagrees) · explained class “{pr['gradcam_class']}” = label class “{label_class}” · API gradcam {f['gradcam_status']}, id {f['id']}",
                 "explained class equals the ensemble label; report both probabilities", {"probe": pr, "facts": f})

    def tc33(self):
        rows = [r for r in self.disagreeing() if not r[1]["heatmap"]]
        if not rows:
            strongest = self.disagreeing()[:1]
            return self.rec("TC-IMG-33", "Not run",
                            "no asset where ResNet18 is near-certain of the other class (no disagreeing asset lost its heatmap; " +
                            (f"strongest disagreement {strongest[0][0]} ResNet18 P(real) {strongest[0][1]['members']['resnet18_robust']:.4f}" if strongest else "no disagreement at all") + ")",
                            "no heatmap with reason → Known limitation", {})
        file, pr = rows[0]
        f = self.submit_probe(file)
        reason = "leaned strongly the other way" in (f["summary"] or "")
        ok = f["gradcam_status"] == "unavailable" and reason and not f["heatmap_path"]
        self.rec("TC-IMG-33", "Known limitation" if ok else "Fail",
                 f"{file}: ensemble P(real) {pr['p_real']:.4f} ({pr['label']}), ResNet18 P(real) {pr['members']['resnet18_robust']:.4f} · API gradcam {f['gradcam_status']}, no heatmap, reason given={reason} · id {f['id']}",
                 "no heatmap and the reason → Known limitation", {"probe": pr, "facts": f})

    def tc34(self):
        f = self.prev("TC-IMG-02") or self.check("img02_urdu_internet.png")[1]
        s = f["summary"] or ""
        ok = "ResNet18" in s and "does not cover the detector's other two models" in s
        old = (self.data["cases"].get("TC-IMG-34") or {}).get("raw", {}).get("web")
        raw = {"summary_excerpt": s[s.find("The Grad-CAM"):][:260], "web": old}
        result = "Fail" if not ok or (old and old.get("ok") is False) else ("Pass" if old and old.get("ok") else "Pass")
        self.rec("TC-IMG-34", result, f"API summary (id {f['id']}): “{short(raw['summary_excerpt'], 150)}”" + (f" · screen: {old['evidence']}" if old else " · screen: see web check"),
                 "caption says ResNet18-based, not CLIP/DINOv2", raw)

    def tc35(self):
        a, b = self.prev("TC-IMG-02"), self.prev("TC-IMG-03")
        used = "02"
        if a and a["branch"] != "image_pair":
            a, used = self.prev("TC-IMG-06"), "06 (substitute: TC-IMG-02 gave no text verdict)"
        if not a or not b:
            return self.rec("TC-IMG-35", "Not run", "needs 02 and 03", "", {})
        text_risk = a["text_confidence"] if a["text_label"] == "Fake" else 1 - a["text_confidence"]
        avg = (text_risk + a["image_score"]) / 2
        ok = abs(a["risk"] - text_risk) < 1e-3 and b["risk"] is None and (abs(a["risk"] - avg) > 1e-3 or abs(text_risk - a["image_score"]) < 1e-3)
        self.rec("TC-IMG-35", "Pass" if ok else "Fail",
                 f"{used}: text {a['text_label']} {a['text_confidence']} → text risk {text_risk:.4f}; final risk {a['risk']}; image_score {a['image_score']} (average would be {avg:.4f}) · 03: no text, risk {b['risk']}, image_score {b['image_score']}",
                 "final risk = text risk; image_score never averaged in; no text → None", {"02": a, "03": b})

    def tc36(self):
        f = self.prev("TC-IMG-02")
        sid = f["id"]
        res = {who: {kind: self.api.get(self.tok[who], f"/submissions/{sid}/{kind}").status_code for kind in ("image", "heatmap")} for who in ("B", "ADMIN")}
        ok = res["B"] == {"image": 404, "heatmap": 404} and res["ADMIN"] == {"image": 200, "heatmap": 200}
        self.rec("TC-IMG-36", "Pass" if ok else "Fail",
                 f"A's id {sid}: user B image {res['B']['image']}, heatmap {res['B']['heatmap']} · admin image {res['ADMIN']['image']}, heatmap {res['ADMIN']['heatmap']}",
                 "404 for B; 200 for admin", res)

    def tc37(self):
        items = self.api.history(self.tok["A"])
        images = [i for i in items if i["submission_type"] == "image"]
        newest = [i["id"] for i in items] == sorted([i["id"] for i in items], reverse=True)
        keys = sorted(images[0].keys()) if images else []
        rejected = {sha(path_of(f).read_bytes()): f for f in ("f04_text_renamed.png", "f04_document.pdf", "f23.gif", "f24_truncated.jpg", "f22b_just_over_10mb.png", "f21_8000x8000.png")}
        listed_rejected, full_ok = [], True
        for i in images:
            stored = self.api.get(self.tok["A"], f"/submissions/{i['id']}/image")
            if stored.status_code == 200 and sha(stored.content) in rejected:
                listed_rejected.append((i["id"], rejected[sha(stored.content)]))
            full = (self.api.get(self.tok["A"], f"/submissions/{i['id']}").json().get("image_submission") or {})
            if full.get("image_analysis_status") == "completed" and full.get("image_score") is None:
                full_ok = False
        list_has = {"ocr text": "ocr_text" in keys, "image_score": "image_score" in keys, "verdict": "final_label" in keys}
        p = ([] if newest else ["not newest first"]) + ([f"rejected file listed: {listed_rejected}"] if listed_rejected else [])
        result = "Fail" if p else ("Pass" if all(list_has.values()) else "Finding")
        self.rec("TC-IMG-37", result,
                 f"{len(images)} image checks, newest first={newest} · list item fields: {', '.join(keys)} · OCR text in list={list_has['ocr text']}, "
                 f"image_score in list={list_has['image_score']}, verdict={list_has['verdict']} · full records carry them={full_ok} · "
                 f"rejected files listed: {len(listed_rejected)} (every listed image's SHA-256 compared with the 6 rejected files)",
                 "newest first with OCR text, verdict, image_score; rejected not listed", {"keys": keys, "count": len(images), "listed_rejected": listed_rejected},
                 notes="" if result != "Finding" else "The history list (SubmissionListItem) has no OCR text and no image_score for image checks; they are only in the full record (text_preview is set for text checks only).")

    def tc38(self):
        runs = [self.check("img02_urdu_internet.png")[1] for _ in range(2)]
        keys = [(r["ocr_text"], r["text_label"], r["text_confidence"], r["image_score"], r.get("heatmap_sha256"), r.get("explained_class")) for r in runs]
        same = keys[0] == keys[1]
        self.rec("TC-IMG-38", "Pass" if same else "Fail",
                 f"ids {runs[0]['id']}, {runs[1]['id']}: OCR text identical={keys[0][0] == keys[1][0]}, verdict {runs[0]['text_label']} {runs[0]['text_confidence']} / {runs[1]['text_label']} {runs[1]['text_confidence']}, image_score {runs[0]['image_score']} / {runs[1]['image_score']}, heatmap bytes identical={keys[0][4] == keys[1][4]}, explained class {runs[0].get('explained_class')}",
                 "identical OCR, verdict, image_score, explained class", {"runs": runs})

    def tc39(self):
        file = "f01_64x64.png"
        res, threads = [None] * 11, []

        def go(i):
            res[i] = self.api.upload(self.tok["A"], file, timeout=900)
            res[i]["t_start"] = round(starts[i], 2)

        t0 = time.perf_counter()
        starts = [0.0] * 11
        for i in range(11):
            starts[i] = time.perf_counter() - t0
            th = threading.Thread(target=go, args=(i,)); th.start(); threads.append(th)
            time.sleep(0.4)      # staggered so the arrival order is 1..11, all inside a few seconds
        for th in threads:
            th.join()
        rb = self.api.upload(self.tok["B"], file, timeout=900)
        statuses = [r["status"] for r in res]
        ok = statuses[:10] == [201] * 10 and statuses[10] == 429 and rb["status"] == 201
        last = res[10]
        self.rec("TC-IMG-39", "Pass" if ok else "Fail",
                 f"A: 11 uploads started within {starts[-1]:.1f} s → statuses {statuses} · 11th: {last['status']} “{last['body'].get('detail')}” Retry-After {last['retry_after']} (answered in {last['latency_s']} s) · B: {rb['status']}",
                 "first 10 succeed; 11th 429 with clear message; B unaffected",
                 {"statuses": statuses, "starts": starts, "eleventh": {"status": last["status"], "detail": last["body"].get("detail")}, "b": rb["status"]},
                 notes="" if ok else "Check that the server runs with the real limit (CHECK_RATE_LIMIT_PER_MINUTE=10).")

    ORDER = [f"TC-IMG-{n:02d}" for n in (2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27,
                                         1, 28, 29, 30, 31, 32, 33, 34, 35, 36, 38, 37)]

    def run_all(self, only):
        health = self.api.http.get(self.api.base + "/health").json()
        assert (health.get("database") or {}).get("database") == "sqlite", "refusing: the server under test must use the throwaway SQLite database"
        self.data["meta"].update({"date": self.args.date, "base_url": self.args.base_url, "server_models": health.get("models"),
                                  "server_environment": health.get("environment")})
        todo = only or self.ORDER
        if any(c in todo for c in ("TC-IMG-32", "TC-IMG-33", "TC-IMG-38")) or not self.probe:
            self.ensure_probe()
        for cid in todo:
            fn = getattr(self, "tc" + cid[-2:], None)
            if fn is None:
                print(f"{cid}: screen case (web_image_cases.py)")
                continue
            try:
                fn()
            except Exception as exc:
                self.rec(cid, "Fail", f"runner error: {type(exc).__name__}: {exc}"[:300], "", {"error": repr(exc)})
            save(self.json_path, self.data)


def save(json_path: Path, data: dict) -> None:
    json_path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    with open(json_path.with_suffix(".csv"), "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(["ID", "Result", "Actual result / evidence"])
        for cid in IDS:
            c = data["cases"].get(cid)
            if c:
                w.writerow([cid, c["result"], c["evidence"] + (f" — {c['notes']}" if c.get("notes") and c["result"] != "Pass" else "")])
            else:
                w.writerow([cid, "Not run", "not run yet"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://127.0.0.1:8001")
    ap.add_argument("--run-dir", required=True, help="the start_test_server.py --run-dir of the server under test")
    ap.add_argument("--only", action="append", default=[])
    ap.add_argument("--date", default=date.today().isoformat())
    ap.add_argument("--probe-child", default=None, help=argparse.SUPPRESS)
    ap.add_argument("--fault-child", default=None, help=argparse.SUPPRESS)
    args = ap.parse_args()
    run = Path(args.run_dir).resolve()
    if args.probe_child:
        child_env(f"sqlite:{run / 'test.db'}", str(run / "uploads"))
        probe_child(json.loads(args.probe_child))
        return
    if args.fault_child:
        fault_child(json.loads(args.fault_child), f"sqlite:{run / 'test.db'}", str(run / "uploads"))
        return
    Runner(args).run_all(args.only)


if __name__ == "__main__":
    main()
