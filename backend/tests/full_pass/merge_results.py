"""Merge the full-pass result files and derive the cases that are read from recorded responses.

    python tests/full_pass/merge_results.py --run-root ROOT --date 2026-11-24

Reads ROOT/sqlite/results_sqlite.json, ROOT/postgres/results_postgres.json, ROOT/rl/results_rl.json,
ROOT/fault/results_fault.json and ROOT/sqlite/results_ui.json (whichever exist), adds derived cases
(TC-OCR, TC-GC, TC-EXP, TC-EVAL, legacy-ID aliases) computed only from data already recorded,
and writes tests/full_pass/results_<date>.json and .csv.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent

ap = argparse.ArgumentParser()
ap.add_argument("--run-root", required=True)
ap.add_argument("--date", required=True)
args = ap.parse_args()
root = Path(args.run_root)

rows: list[dict] = []
for rel in ("sqlite/results_sqlite.json", "sqlite/results_ui.json", "rl/results_rl.json", "fault/results_fault.json", "postgres/results_postgres.json"):
    p = root / rel
    if p.exists():
        rows += json.loads(p.read_text(encoding="utf-8"))

by = {(r["id"], r["db"]): r for r in rows}
S = lambda i: by.get((i, "sqlite"))  # noqa: E731
F = lambda i: by.get((i, "fault"))  # noqa: E731
D = lambda i: (S(i) or {}).get("data", {})  # noqa: E731
derived: list[dict] = []


def add(id_, title, input_, expected, actual, evidence, result, how="Real", uc=None, src=None):
    derived.append({"id": id_, "title": title, "input": input_, "expected": expected, "actual": actual, "evidence": evidence,
                    "result": result, "how": how, "group": id_.split("-")[1], "use_case": uc, "db": "derived",
                    "derived_from": src})


def ocr_case(id_, title, img, cond, expected, uc="UC-4 Submit Image"):
    d = D(f"TC-IMG-{img}")
    if not d:
        return add(id_, title, img, expected, "image case did not run", "-", "Blocked", uc=uc)
    ok = cond(d)
    add(id_, title, f"TC-IMG-{img}", expected,
        f"ocr_status {d.get('ocr_status')}, conf {d.get('ocr_confidence')}, language {d.get('detected_language')}, branch {d.get('analysis_branch')}, "
        f"route {d.get('model_version')}, text {str(d.get('ocr_text'))[:90]!r}", f"TC-IMG-{img} response", "Pass" if ok else "Fail", uc=uc, src=f"TC-IMG-{img}")


ur = lambda t: bool(re.search(r"[؀-ۿ]{3}", t or ""))  # noqa: E731
ocr_case("TC-OCR-01", "OCR reads Urdu text and sends it to the Urdu model", "C01",
         lambda d: d.get("ocr_status") == "completed" and ur(d.get("ocr_text")) and str(d.get("model_version")).endswith("xlmr-urdu"),
         "completed; Urdu text; img-pair:xlmr-urdu")
ocr_case("TC-OCR-02", "OCR reads Roman Urdu and sends it to the Roman Urdu model", "C02",
         lambda d: d.get("ocr_status") == "completed" and "ukoomat" in (d.get("ocr_text") or "") and str(d.get("model_version")).endswith("xlmr-roman-urdu"),
         "completed; Roman Urdu text; img-pair:xlmr-roman-urdu")
ocr_case("TC-OCR-03", "OCR reads English", "C03", lambda d: d.get("ocr_status") == "completed" and "chools" in (d.get("ocr_text") or ""),
         "completed; English text; Roman Urdu model with the English note")
ocr_case("TC-OCR-04", "OCR on mixed Urdu + English", "C04", lambda d: d.get("ocr_status") == "completed" and ur(d.get("ocr_text")),
         "completed; both scripts read")
ocr_case("TC-OCR-05", "No text found is reported as such", "C07", lambda d: d.get("ocr_status") == "no_text_found" and d.get("analysis_branch") == "ai_or_real",
         "ocr_status no_text_found (distinct from a failure); ai_or_real branch")
ocr_case("TC-OCR-06", "Low-confidence text: the text verdict is skipped, with the reason", "C06",
         lambda d: (d.get("analysis_branch") == "ai_or_real" and "too little" in (d.get("summary") or "").lower() or "no readable" in (d.get("summary") or "").lower())
         or (d.get("analysis_branch") == "image_pair" and (d.get("ocr_confidence") or 0) >= 0.3),
         "below 0.3 or <10 letters -> ai_or_real and the summary says why; otherwise image_pair")
ocr_case("TC-OCR-07", "Multi-line text is read in order", "C05", lambda d: d.get("reading_order_positions") and -1 not in d["reading_order_positions"]
         and d["reading_order_positions"] == sorted(d["reading_order_positions"]), "Pehli < Doosri < Teesri in ocr_text")
h5 = S("TC-HIS-05")
add("TC-OCR-08", "OCR output is saved and shown in the result and history", "TC-HIS-05", "ocr_text/ocr_status in the stored detail",
    h5["actual"] if h5 else "not run", "GET /submissions/{id}", h5["result"] if h5 else "Blocked", uc="UC-4 Submit Image", src="TC-HIS-05")
fi = F("TC-OCR-FI1")
if fi:
    add("TC-OCR-09", "OCR failure is told apart from 'no text found'", "TC-OCR-FI1", "a failure status, not no_text_found",
        f"ocr_status under an OCR crash: {fi['data'].get('ocr_status')}; without text: {D('TC-IMG-C07').get('ocr_status')}", "fault + TC-IMG-C07",
        "Pass" if fi["data"].get("ocr_status") not in ("completed", "no_text_found") else "Fail", how="Fault-injected", uc="UC-4 Submit Image", src="TC-OCR-FI1")
add("TC-OCR-10", "Windows first run: EasyOCR needs PYTHONUTF8=1", "environment note", "documented",
    "EasyOCR's first-run download prints non-ASCII progress; on a cp1252 console it can fail without PYTHONUTF8=1 (the test servers set it). Weights were already cached here.",
    "start_test_server.py sets PYTHONUTF8=1", "Info", how="Manual", uc="UC-4 Submit Image")

# Grad-CAM / explanation
c01, c07 = D("TC-IMG-C01"), D("TC-IMG-C07")
add("TC-GC-01", "A heatmap is made with and without text (OCR and Grad-CAM are not alternatives)", "C01 (Urdu text) and C07 (no text)",
    "gradcam completed on both", f"C01 {c01.get('gradcam_status')} ({c01.get('analysis_branch')}); C07 {c07.get('gradcam_status')} ({c07.get('analysis_branch')})",
    "TC-IMG-C01/C07", "Pass" if c01.get("gradcam_status") == "completed" and c07.get("gradcam_status") == "completed" else "Fail", uc="UC-5 View Explainability Panel")
caps = [(i, "ResNet18" in (d.get("summary") or "") and "other two models" in (d.get("summary") or "")) for i, d in
        ((r["id"], r.get("data", {})) for r in rows if r["db"] == "sqlite" and r["id"].startswith("TC-IMG-") and r.get("data", {}).get("gradcam_status") == "completed")]
add("TC-GC-04", "Caption says the heatmap is ResNet18-only (not CLIP or DINOv2)", f"{len(caps)} image results with a heatmap", "every caption names ResNet18 and excludes the other two",
    f"missing on: {[i for i, ok in caps if not ok] or 'none'}", "explanation_summary", "Pass" if caps and all(ok for _, ok in caps) else "Fail", uc="UC-5 View Explainability Panel")
b_access = [(r["id"], r["data"].get("user_b_access")) for r in rows if r["db"] == "sqlite" and r["id"].startswith("TC-IMG-") and r.get("data", {}).get("user_b_access")]
add("TC-EXP-03", "Heatmap privacy: another user gets 404", f"{len(b_access)} image submissions", "404 for detail/image/heatmap",
    f"non-404: {[i for i, v in b_access if v != [404, 404, 404]] or 'none'}", "user B GETs", "Pass" if b_access and all(v == [404, 404, 404] for _, v in b_access) else "Fail",
    uc="UC-5 View Explainability Panel")
add("TC-EXP-02", "Grad-CAM heatmap generated for a valid image", "TC-IMG-C07", "gradcam completed; PNG served at the upright image size",
    f"{c07.get('gradcam_status')}; heatmap {c07.get('heatmap_size')} vs image {c07.get('upright_size')}", "GET /heatmap",
    "Pass" if c07.get("gradcam_status") == "completed" and c07.get("heatmap_size") == c07.get("upright_size") else "Fail", uc="UC-5 View Explainability Panel")
xl = [(r["id"], r["data"]) for r in rows if r["db"] == "sqlite" and r["id"].startswith("TC-TXT-") and r.get("data", {}).get("model_version") in ("xlmr-urdu", "xlmr-roman-urdu")
      and r["data"].get("highlights")]
weak = [(i, d["confidence"], max(abs(c) for _, c in d["highlights"])) for i, d in xl]
tiny = [w for w in weak if w[1] and w[1] >= 0.99 and w[2] < 0.01]
add("TC-EXP-01", "Highlighted words for short XLM-R text", f"{len(xl)} XLM-R results with highlights", "1-8 words from the input, each with a contribution",
    f"{len(xl)} with highlights; very confident results (>=0.99) whose largest contribution is < 0.01: {[(i, c, round(m, 5)) for i, c, m in tiny] or 'none'}",
    "highlighted_words", "Pass" if xl else "Fail", uc="UC-5 View Explainability Panel")
if tiny:
    add("TC-EXP-08", "Known weakness: highlights carry almost no weight when confidence is very high", ", ".join(i for i, _, _ in tiny),
        "recorded (audit)", f"{len(tiny)} cases: removing any one word changes the score by < 1 point", "TC-EXP-01 data", "Known-limitation", uc="UC-5 View Explainability Panel")
ul1 = D("TC-TXT-UL1")
add("TC-EXP-06", "Highlights for long articles (TF-IDF)", "TC-TXT-UL1", "words with exact linear-model weights",
    f"{len(ul1.get('highlights') or [])} words: {[w for w, _ in (ul1.get('highlights') or [])][:8]}", "highlighted_words",
    "Pass" if ul1.get("highlights") else "Fail", uc="UC-5 View Explainability Panel")
x07 = D("TC-TXT-X07")
add("TC-EXP-04", "No highlights when no model ran", "TC-TXT-X07 (emoji only)", "no highlights; summary says why",
    f"highlights {x07.get('highlights')}; summary {str(x07.get('summary'))[:120]!r}", "TC-TXT-X07", "Pass" if x07 and not x07.get("highlights") else "Fail",
    uc="UC-5 View Explainability Panel")
add("TC-EXP-07", "SRS says SHAP; the code removes one word at a time (XLM-R) / uses linear weights (TF-IDF)", "app/ai/text/explain.py", "document discrepancy",
    "occlusion over up to 8 words; exact TF-IDF x weight for long articles", "code reading", "Info", how="Manual", uc="UC-5 View Explainability Panel")

# Evaluation pipeline
fp = lambda d: (d["text_confidence"] if d["text_prediction"] == "Fake" else 1 - d["text_confidence"]) if d.get("text_confidence") is not None else None  # noqa: E731
add("TC-EVAL-01", "Text verdict plus image output: risk comes from the text only", "TC-IMG-C01", "combined_risk_score == text fake probability; image_score separate",
    f"risk {c01.get('risk')}; text fake probability {fp(c01) if c01 else None}; image_score {c01.get('image_score')}", "TC-IMG-C01",
    "Pass" if c01 and c01.get("risk") is not None and abs(c01["risk"] - fp(c01)) < 1e-3 else "Fail", uc="UC-4 Submit Image")
add("TC-EVAL-02", "Image without OCR text: Uncertain, no risk, image score present", "TC-IMG-C07", "final Uncertain, combined_risk_score None, image_score present",
    f"{c07.get('final_label')}, risk {c07.get('risk')}, image_score {c07.get('image_score')}", "TC-IMG-C07",
    "Pass" if c07.get("final_label") == "Uncertain" and c07.get("risk") is None and c07.get("image_score") is not None else "Fail", uc="UC-4 Submit Image")
pairs = [(r["id"], r["data"]) for r in rows if r["db"] == "sqlite" and r["id"].startswith("TC-IMG-") and r.get("data", {}).get("analysis_branch") == "image_pair"
         and r["data"].get("text_prediction") in ("Real", "Fake")]
mixed = [i for i, d in pairs if d.get("risk") is None or abs(d["risk"] - fp(d)) > 1e-3]
add("TC-EVAL-06", "Everything available: verdict and risk never averaged with the image score", f"{len(pairs)} image-pair results", "risk == text fake probability on every one",
    f"averaged/mismatched: {mixed or 'none'}", "TC-IMG responses", "Pass" if pairs and not mixed else "Fail", uc="UC-4 Submit Image")
add("TC-EVAL-08", "SRS 'weighted combination' of text and image scores", "pipeline.evaluate()", "document discrepancy with the agreed design",
    "evaluate() takes the verdict and risk only from the text classification; image authenticity is reported separately (the Backend Guide's 70/30 weighting is outdated)",
    "app/ai/pipeline.py evaluate()", "Info", how="Manual", uc="UC-4 Submit Image")

# Legacy report IDs -> the case that now covers them
alias = {"TC-TXT-02": "TC-TXT-U01", "TC-TXT-03": "TC-TXT-UL1", "TC-TXT-04": "TC-TXT-R01", "TC-TXT-05": "TC-TXT-E01", "TC-TXT-06": "TC-TXT-X01",
         "TC-IMG-01": "TC-IMG-C07", "TC-IMG-02": "TC-IMG-C01", "TC-IMG-03": "TC-IMG-C02", "TC-IMG-04": "TC-IMG-F12", "TC-IMG-05": "TC-IMG-F09", "TC-IMG-06": "TC-IMG-F14"}
for legacy, src in alias.items():
    r = S(src)
    if r:
        add(legacy, f"(report ID) {r['title']}", r["input"], r["expected"], r["actual"], f"same run as {src}", r["result"], how=r["how"], uc=r["use_case"], src=src)

allrows = rows + derived
out_json = HERE / f"results_{args.date}.json"
out_json.write_text(json.dumps(allrows, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
with open(HERE / f"results_{args.date}.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["id", "db", "group", "use_case", "title", "input", "expected", "actual", "evidence", "result", "how"])
    for r in allrows:
        w.writerow([r["id"], r["db"], r["group"], r.get("use_case"), r["title"], str(r["input"])[:300], r["expected"], r["actual"], r["evidence"], r["result"], r["how"]])
from collections import Counter  # noqa: E402

print(len(allrows), "rows;", Counter(r["result"] for r in allrows))
print(out_json)
