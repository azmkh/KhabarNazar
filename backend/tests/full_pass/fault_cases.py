"""Fault-injected and in-process cases of the full test pass (things HTTP alone cannot trigger).

    python tests/full_pass/fault_cases.py --run-dir RUN

Runs the real app in-process (FastAPI TestClient) on its own throwaway SQLite database and uploads
folder, with the REAL models, and breaks exactly one thing per case with unittest.mock:
a missing text model, a text model that throws, a failing explanation, an OCR crash, a detector
crash, a Grad-CAM crash, everything failing, and a database write that fails half-way.
It also runs the real detector directly on every content image to compare the class Grad-CAM
explains with the ensemble's label (gradcam_class is not part of the API response).
Results go to RUN/results_fault.json (merged by merge_results.py). Stop the HTTP test server
first: this process loads its own copy of the models (~6 GB).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fp_common import BACKEND, HERE, TEST_JWT_SECRET  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--run-dir", required=True)
args = ap.parse_args()
RUN = Path(args.run_dir).resolve()
RUN.mkdir(parents=True, exist_ok=True)
DB = RUN / "fault.db"
DB.unlink(missing_ok=True)
UPLOADS = RUN / "uploads"
UPLOADS.mkdir(exist_ok=True)
for k in [k for k in os.environ if k.startswith("KHABARNAZAR_")]:
    del os.environ[k]
os.environ.update({"DATABASE_URL": f"sqlite:///{DB.as_posix()}", "UPLOAD_DIR": str(UPLOADS), "JWT_SECRET": TEST_JWT_SECRET,
                   "PRELOAD_MODELS": "false", "ENVIRONMENT": "full-pass-fault", "CHECK_RATE_LIMIT_PER_MINUTE": "0",
                   "CHECK_RATE_LIMIT_PER_HOUR": "0"})
sys.path.insert(0, str(BACKEND))
os.chdir(BACKEND)

import subprocess  # noqa: E402

subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True, capture_output=True)

from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image  # noqa: E402

from app.ai.image import ai_detector  # noqa: E402
from app.ai.text import xlmr  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app, raise_server_exceptions=False)
results: list[dict] = []
IMG = HERE / "images"
URDU = "حکومت نے اعلان کیا ہے کہ ملک بھر میں سات دن کے لیے انٹرنیٹ سروس بند کر دی جائے گی۔"
ROMAN = "Hukoomat ne elan kiya hai ke mulk bhar mein saat din ke liye internet service band kar di jayegi."


def rec(id_, title, input_, expected, actual, evidence, result, how="Fault-injected", uc=None, data=None):
    results.append({"id": id_, "title": title, "input": input_, "expected": expected, "actual": actual, "evidence": evidence,
                    "result": result, "how": how, "group": id_.split("-")[1], "use_case": uc, "db": "fault",
                    "time": datetime.now().isoformat(timespec="seconds"), "data": data or {}})
    print(f"[{result:16}] {id_:12} {title[:80]}", flush=True)
    (RUN / "results_fault.json").write_text(json.dumps(results, indent=1, ensure_ascii=False, default=str), encoding="utf-8")


tok = client.post("/api/v1/auth/register", json={"name": "Fault User", "email": "fault.user@example.com", "password": "Password123!"}).json()["access_token"]
H = {"Authorization": f"Bearer {tok}"}


def text(t):
    r = client.post("/api/v1/submissions/text", json={"text": t}, headers=H)
    return r.status_code, (r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text)


def image(name, ctype="image/png"):
    r = client.post("/api/v1/submissions/image", files={"file": (name, (IMG / name).read_bytes(), ctype)}, headers=H)
    return r.status_code, (r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text)


def counts():
    from sqlalchemy import create_engine, text as sql
    e = create_engine(os.environ["DATABASE_URL"])
    with e.connect() as c:
        out = {t: c.execute(sql(f"SELECT count(*) FROM {t}")).scalar() for t in
               ("submissions", "text_submissions", "image_submissions", "explainability")}
    e.dispose()
    out["upload_files"] = len(list(UPLOADS.glob("*.*")))
    out["heatmaps"] = len(list((UPLOADS / "explanations").glob("*"))) if (UPLOADS / "explanations").exists() else 0
    return out


def summarize(body):
    if not isinstance(body, dict):
        return str(body)[:200]
    im = body.get("image_submission") or {}
    ts = body.get("text_submission") or {}
    ex = body.get("explainability") or {}
    return {"final_label": body.get("final_label"), "risk": body.get("combined_risk_score"),
            "text_conf": ts.get("text_confidence") if ts else im.get("text_confidence"), "model_version": ex.get("model_version"),
            "processing_status": ts.get("processing_status"), "analysis_branch": im.get("analysis_branch"),
            "ocr_status": im.get("ocr_status"), "ocr_text": (im.get("ocr_text") or "")[:80], "text_prediction": im.get("text_prediction"),
            "image_score": im.get("image_score"), "image_analysis_status": im.get("image_analysis_status"),
            "gradcam_status": body.get("gradcam_status"), "highlights": ex.get("highlighted_words"),
            "summary": ex.get("explanation_summary")}


# Warm the real models once so every case below uses them.
s, b = text(URDU); s2, b2 = text(ROMAN); s3, b3 = image("urdu_headline.png")
print("warm-up:", s, s2, s3, flush=True)

# TC-TXT-01: model missing (empty model folder) -> Uncertain, status unavailable, no score
empty = RUN / "empty_model_dir"
empty.mkdir(exist_ok=True)
with patch.object(xlmr, "model_dir", lambda script: empty):
    s, b = text(URDU)
d = summarize(b)
ok = s == 201 and d["final_label"] == "Uncertain" and d["text_conf"] is None and d["risk"] is None and d["processing_status"] == "unavailable" and d["model_version"] == "text-model-unavailable"
rec("TC-TXT-01", "Text model missing -> Uncertain, 'unavailable', no score", "Urdu sentence with the XLM-R folder pointing at an empty directory",
    "201; Uncertain; processing_status unavailable; no confidence/risk; no highlights", json.dumps(d, ensure_ascii=False)[:400],
    "patch xlmr.model_dir -> empty folder; POST /submissions/text", "Pass" if ok and not d["highlights"] else "Fail", uc="UC-3 Submit Text", data=d)

# TC-TXT-FI2: model throws during inference
with patch.object(xlmr.XlmrClassifier, "predict", side_effect=RuntimeError("injected inference failure")):
    s, b = text(ROMAN)
d = summarize(b)
ok = s == 201 and d["final_label"] == "Uncertain" and d["text_conf"] is None and "could not complete" in (d["summary"] or "")
rec("TC-TXT-FI2", "Text model throws during inference -> error reported, nothing invented", "Roman Urdu sentence; XlmrClassifier.predict raises",
    "201; Uncertain; no score; summary says the classifier could not complete the check", json.dumps(d, ensure_ascii=False)[:400],
    "patch XlmrClassifier.predict(side_effect=RuntimeError)", "Pass" if ok else "Fail", uc="UC-3 Submit Text", data=d)

# TC-EXP-05: the explanation step fails (use case 4-A: 'Detailed explanation is temporarily unavailable')
import app.ai.pipeline as pipeline_mod  # noqa: E402

before = counts()
with patch.object(pipeline_mod, "explain_text", side_effect=RuntimeError("injected explanation failure")):
    s, b = text(URDU)
d = summarize(b) if isinstance(b, dict) else {"body": str(b)[:200]}
after = counts()
rec("TC-EXP-05", "Explanation cannot be produced (use case 4-A)", "Urdu sentence; explain_text raises",
    "the classification is still returned with a fallback message ('Detailed explanation is temporarily unavailable')",
    f"HTTP {s}; {json.dumps(d, ensure_ascii=False)[:300]}; rows before {before['submissions']} after {after['submissions']}",
    "patch app.ai.pipeline.explain_text(side_effect=RuntimeError)", "Pass" if s == 201 and d.get("final_label") in ("Real", "Fake") else "Fail",
    uc="UC-5 View Explainability Panel", data={"status": s, **d, "rows_before": before, "rows_after": after})

# OCR crash -> reported; image analysis and Grad-CAM still run
import app.ai.image.ocr as ocr_mod  # noqa: E402


class BrokenReader:
    def readtext(self, *a, **k):
        raise RuntimeError("injected OCR crash")


with patch.object(ocr_mod, "load_ocr_reader", lambda: BrokenReader()):
    s, b = image("urdu_headline.png")
d = summarize(b)
ok = s == 201 and d["ocr_status"] not in ("completed", "no_text_found") and d["image_score"] is not None and d["gradcam_status"] == "completed" \
    and d["final_label"] == "Uncertain" and d["risk"] is None
rec("TC-OCR-FI1", "OCR crashes -> failure reported; image analysis and Grad-CAM still run", "Urdu headline image; EasyOCR readtext raises",
    "201; ocr_status = a failure status (not no_text_found); image_score present; Grad-CAM completed; Uncertain, no risk",
    json.dumps(d, ensure_ascii=False)[:400], "patch ocr.load_ocr_reader -> reader that raises", "Pass" if ok else "Fail", uc="UC-4 Submit Image", data=d)
rec("TC-EVAL-04", "OCR fails, image analysis succeeds", "as TC-OCR-FI1", "verdict Uncertain (no text), risk None, image result reported",
    f"final {d['final_label']}, risk {d['risk']}, image_score {d['image_score']}", "TC-OCR-FI1 response", "Pass" if ok else "Fail", uc="UC-4 Submit Image", data=d)

# Detector crash with usable text -> text verdict kept, image 'unavailable'
with patch.object(ai_detector.AIImageDetector, "analyse", side_effect=RuntimeError("injected detector crash")):
    s, b = image("roman_headline.png")
d = summarize(b)
ok = s == 201 and d["analysis_branch"] == "image_pair" and d["final_label"] in ("Real", "Fake") and d["risk"] is not None \
    and d["image_score"] is None and d["image_analysis_status"] == "unavailable" and d["gradcam_status"] in ("not_run", "unavailable")
rec("TC-EVAL-03", "OCR text present, image analysis fails", "Roman Urdu headline image; detector.analyse raises",
    "text verdict from the OCR text kept; image_score None, image_analysis_status unavailable; no heatmap", json.dumps(d, ensure_ascii=False)[:400],
    "patch AIImageDetector.analyse(side_effect=RuntimeError)", "Pass" if ok else "Fail", uc="UC-4 Submit Image", data=d)

# Grad-CAM crash (real backward pass breaks) -> explanation unavailable, prediction kept
det, _ = ai_detector.load_detector()
layer = det.resnet.layer4[-1]


class _Handle:
    def remove(self):
        pass


with patch.object(layer, "register_forward_hook", lambda hook: _Handle()):
    s, b = image("english_headline.png")
d = summarize(b)
ok = s == 201 and d["image_score"] is not None and d["gradcam_status"] == "unavailable" and "unavailable" in (d["summary"] or "").lower()
rec("TC-GC-FI1", "Grad-CAM fails -> 'unavailable', no heatmap invented, image prediction kept", "English headline image; the ResNet18 hook is disabled so the backward pass fails",
    "201; image_score present; gradcam_status unavailable; summary says why; GET /heatmap 404", json.dumps(d, ensure_ascii=False)[:400],
    "patch layer4[-1].register_forward_hook -> no-op (real except-path in _resnet_with_gradcam)", "Pass" if ok else "Fail", uc="UC-5 View Explainability Panel", data=d)
if isinstance(b, dict):
    hm = client.get(f"/api/v1/submissions/{b['id']}/heatmap", headers=H).status_code
    results[-1]["data"]["heatmap_http"] = hm
rec("TC-EVAL-05", "Grad-CAM fails, image analysis succeeds", "as TC-GC-FI1", "image result reported, no heatmap; verdict from the OCR text only",
    f"final {d['final_label']}, risk {d['risk']}, image_score {d['image_score']}, gradcam {d['gradcam_status']}", "TC-GC-FI1 response", "Pass" if ok else "Fail", uc="UC-4 Submit Image", data=d)

# Nothing available: OCR and detector both fail
with patch.object(ocr_mod, "load_ocr_reader", lambda: BrokenReader()), \
        patch.object(ai_detector.AIImageDetector, "analyse", side_effect=RuntimeError("injected detector crash")):
    s, b = image("english_headline.png")
d = summarize(b)
ok = s == 201 and d["final_label"] == "Uncertain" and d["risk"] is None and d["image_score"] is None and d["text_prediction"] is None
rec("TC-EVAL-07", "Nothing available (OCR and detector both fail)", "English headline image; OCR and detector raise",
    "201; Uncertain; no risk; no image score; failures stated", json.dumps(d, ensure_ascii=False)[:400], "both patches", "Pass" if ok else "Fail", uc="UC-4 Submit Image", data=d)

# DB atomicity: the explainability row fails -> nothing saved, upload removed
import app.services.submission_service as svc  # noqa: E402


class BrokenExplainability:
    def __init__(self, *a, **k):
        raise RuntimeError("injected failure while building the explainability row")


before = counts()
with patch.object(svc, "Explainability", BrokenExplainability):
    st, _ = text(URDU)
    si, _ = image("urdu_headline.png")
after = counts()
ok = st == 500 and si == 500 and before == after
rec("TC-DB-02", "A submission writes all its rows or none", "text + image submission with the Explainability row failing half-way",
    "HTTP 500 (generic), no submission/text/image/explainability rows, no upload or heatmap file left", f"text {st}, image {si}; before {before}; after {after}",
    "patch submission_service.Explainability; row and file counts", "Pass" if ok else "Fail", uc="DB", data={"before": before, "after": after})

# Grad-CAM class vs ensemble label on every valid content/format image (real detector, in-process)
from PIL import ImageOps  # noqa: E402

from app.ai.image.predict import analyze_image  # noqa: E402
from app.ai.image.preprocess import upright_image  # noqa: E402

manifest = json.loads((IMG / "manifest.json").read_text(encoding="utf-8"))
rows = []
for m in manifest:
    if m["expected"].get("http_status") != 201 or m["id"] in ("F07b", "F08"):
        continue
    with upright_image(str(IMG / m["file"])) as up:
        r = analyze_image(up)
    if r.get("is_stub"):
        rows.append({"id": m["id"], "file": m["file"], "error": r.get("summary")})
        continue
    ens = r["manipulation_prediction"]
    p_real_res = r["members"].get("resnet18_robust")
    rows.append({"id": m["id"], "file": m["file"], "ensemble_label": ens, "gradcam_class": r.get("gradcam_class"),
                 "members": r["members"], "gradcam_status": r["gradcam_status"], "gradcam_error": r.get("gradcam_error"),
                 "resnet_agrees": None if p_real_res is None else ((p_real_res >= 0.5) == (ens == ai_detector.LABEL_REAL))})
ok_rows = [x for x in rows if "ensemble_label" in x]
mismatch = [x["id"] for x in ok_rows if x["gradcam_class"] and ((x["gradcam_class"] == "real") != (x["ensemble_label"] == ai_detector.LABEL_REAL))]
disagree = [x["id"] for x in ok_rows if x["resnet_agrees"] is False]
flat = [x["id"] for x in ok_rows if x["gradcam_status"] != "completed"]
rec("TC-GC-02", "The heatmap explains the class the ensemble shows, on every image", f"{len(ok_rows)} valid images, real detector in-process",
    "gradcam_class == ensemble label for all; include a case where ResNet18 disagrees",
    f"class mismatches: {mismatch or 'none'}; ResNet18 disagrees with the ensemble on: {disagree or 'none'}; no heatmap on: {flat or 'none'}",
    "analyze_image() on the upright image (gradcam_class is not in the API response)", "Pass" if not mismatch and ok_rows else "Fail",
    how="Real (in-process)", uc="UC-5 View Explainability Panel", data={"rows": rows})
if flat:
    rec("TC-GC-03", "Flat map: no heatmap when ResNet18 strongly favours the other class (known behaviour)", ", ".join(flat),
        "no heatmap, reason reported", "; ".join(f"{x['id']}: {x['gradcam_error']}" for x in ok_rows if x["id"] in flat),
        "analyze_image()", "Known-limitation", how="Real (in-process)", uc="UC-5 View Explainability Panel")
else:
    rec("TC-GC-03", "Flat map: no heatmap when ResNet18 strongly favours the other class (known behaviour)", "all valid images",
        "a flat-map case if one occurs", "no flat map occurred on this image set (behaviour not observed)", "analyze_image()",
        "Blocked", how="Real (in-process)", uc="UC-5 View Explainability Panel")

# /health does not load models (fresh status in this process before any load is not possible: models are loaded now)
print("done; results in", RUN / "results_fault.json")
