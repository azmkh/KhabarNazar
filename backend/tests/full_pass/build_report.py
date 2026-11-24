"""Build docs/testing/FULL_TEST_REPORT_<date>.md from results_<date>.json and the run folders.

    python tests/full_pass/build_report.py --date 2026-11-24 --run-root ROOT

The tables are generated from the recorded results; the defect log, design discrepancies and
findings below are written by hand from those results (each names the case that shows it).
"""
from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]

ap = argparse.ArgumentParser()
ap.add_argument("--date", required=True)
ap.add_argument("--run-root", required=True)
args = ap.parse_args()
root = Path(args.run_root)
rows = json.loads((HERE / f"results_{args.date}.json").read_text(encoding="utf-8"))
load = lambda p: json.loads((root / p).read_text(encoding="utf-8-sig")) if (root / p).exists() else {}  # noqa: E731
startup, ram = load("postgres/startup.json"), load("sqlite/ram.json")
st_sqlite, st_pg = load("sqlite/state_sqlite.json"), load("postgres/state_postgres.json")

alias_of = {r["derived_from"]: r["id"] for r in rows if r["db"] == "derived" and r.get("derived_from") and r["title"].startswith("(report ID)")}
real = [r for r in rows if not (r["db"] == "derived" and r["title"].startswith("(report ID)")) and r["id"] != "SETUP-01"]
# A case counts as Blocked only if it ran nowhere; any failure anywhere makes it Fail.
RANK = {"Fail": 4, "Known-limitation": 3, "Pass": 2, "Blocked": 1, "Info": 0}
DBNAME = {"sqlite": "SQLite", "postgres": "PostgreSQL", "rl": "real limits", "fault": "fault-injected", "ui": "browser", "derived": "derived"}
cases: dict[str, dict] = {}
for r in real:
    c = cases.setdefault(r["id"], {"row": r, "results": {}})
    c["results"][r["db"]] = r["result"]
    PRIORITY = ["sqlite", "ui", "rl", "fault", "derived", "postgres"]
    if PRIORITY.index(r["db"]) < PRIORITY.index(c["row"]["db"]):
        c["row"] = r
for c in cases.values():
    c["final"] = max(c["results"].values(), key=lambda v: RANK[v])

SECTION = {"UC-1 User Registration": "UC-1", "UC-2 Login": "UC-2", "UC-3 Submit Text": "UC-3", "UC-4 Submit Image": "UC-4",
           "UC-5 View Explainability Panel": "UC-5", "UC-6 Dispute AI Prediction": "UC-6", "UC-7 View Submission History": "UC-7",
           "UC-8 Admin Reviews Dispute": "UC-8", "UC-9 Admin Views All Submissions": "UC-9"}
GROUP_SECTION = {"SEC": "SEC", "RL": "RL", "DB": "DB", "APP": "APP", "PERF": "PERF", "NAV": "NAV"}


def section_of(r):
    uc = r.get("use_case")
    if uc in SECTION:
        return SECTION[uc]
    if r["id"].startswith("TC-NAV"):
        return "NAV"
    if uc in ("App-backend",):
        return "APP"
    if uc == "Profile":
        return "UC-2"
    if uc == "DB" or r["group"] == "DB":
        return "DB"
    return GROUP_SECTION.get(r["group"], r["group"])


by_section: dict[str, list] = defaultdict(list)
for cid, c in cases.items():
    by_section[section_of(c["row"])].append(cid)

UC_META = {
    "UC-1": ("User Registration", "Create an account with name, email and password; reject invalid or duplicate data."),
    "UC-2": ("Login (and session handling)", "Sign in, keep or end a session safely, lock out password guessing; profile and sign-out screens."),
    "UC-3": ("Submit Text", "Check Urdu, Roman Urdu, English, mixed and edge-case text with the real models; route, label, score, explanation, history."),
    "UC-4": ("Submit Image", "Upload images; OCR + text classification and AI-or-real detection always run; formats, rejection, evaluation rules."),
    "UC-5": ("View Explainability Panel", "Word highlights for text, Grad-CAM heatmaps for images, their captions, privacy and failure handling."),
    "UC-6": ("Dispute AI Prediction", "File a dispute with a justification and optional evidence link; rules and status display."),
    "UC-7": ("View Submission History", "List, page and open own submissions; isolation between users; admin decisions shown."),
    "UC-8": ("Admin Reviews Dispute", "Admin queue, uphold/override with a required comment, the user sees the decision."),
    "UC-9": ("Admin Views All Submissions", "Admin list of every submission, dashboard counts, access to any result."),
    "SEC": ("Security and robustness (TC-SEC)", "Authentication on every route, ownership, path traversal, oversized bodies, CORS, error hygiene, /health."),
    "RL": ("Rate limit (TC-RL, deploy branch only)", "Per-user limit on checks with the real 10/min setting."),
    "DB": ("Database (TC-DB)", "Schema vs documentation; all-or-nothing writes."),
    "APP": ("App-backend connection (TC-APP)", "lib/api.ts paths and fields match the backend; timeouts; unreachable backend."),
    "NAV": ("Navigation and route guard (TC-NAV)", "Deep links, reloads, bad tokens and admin-only routes in the web app."),
    "PERF": ("Performance (TC-PERF)", "Latency, start-up time, memory and concurrent requests (recorded, not failed on CPU latency)."),
}
ORDER = ["UC-1", "UC-2", "UC-3", "UC-4", "UC-5", "UC-6", "UC-7", "UC-8", "UC-9", "SEC", "RL", "DB", "APP", "NAV", "PERF"]


def cell(v, n):
    s = " ".join(str(v).split())
    s = s.replace("|", "\\|")
    return s if len(s) <= n else s[: n - 1] + "…"


def result_cell(c):
    res = c["results"]
    if len(res) == 1:
        return c["final"]
    return f"{c['final']} ({', '.join(f'{DBNAME[k]}: {v}' for k, v in res.items())})"


def sort_key(cid):
    return (cid.split("-")[1], cid)


DEFECTS = [
    ("DEF-01", "A bare URL (or other non-news Latin text) gets a confident verdict", "Medium",
     "POST /api/v1/submissions/text {\"text\": \"https://example.com/news/2026/11/24/story-12345\"}",
     "Uncertain with no score (the test plan: no words to classify), or a 'not news' message",
     "201, detected 'unknown', routed to xlmr-roman-urdu, **Real 72.2 %**, 8 highlighted URL fragments", "TC-TXT-X09",
     "backend/app/ai/text/predict.py:64-74 (model_language: any letters -> classified); language_detection.py", "main, deploy"),
    ("DEF-02", "After an admin override, the result still shows the AI's Score and Fake-news risk next to the admin's label", "Medium",
     "Text 'حکومت نے اعلان کیا…' (AI: Likely misleading 99.9 %) -> dispute -> admin overrides to Credible -> user opens the result",
     "The admin's label without the AI's numbers, or the numbers clearly labelled as the AI's original estimate",
     "Header 'AI VERDICT (OVERRIDDEN) Likely credible' with **Score 99.9 % / Fake-news risk 99.9 %** directly under it", "TC-UI-19 (TC-UI-17); screenshots/UI-17_user_sees_override.png",
     "app/result/[id].tsx:156-164 (HeroStat score/risk always rendered); combined_risk_score kept on override in dispute_service.review_dispute", "main, deploy"),
    ("DEF-03", "The admin's all-submissions list cannot be filtered", "Medium",
     "GET /api/v1/admin/submissions?final_label=Fake (also ?submission_type=image, ?user_email=…); admin Submissions screen",
     "A filter (use case UC-9)", "Parameters ignored (same total 110 for every query); the admin screen has no filter control (History has one)", "TC-ADM-09",
     "backend/app/routers/admin.py:17 (no filter parameters); app/admin/submissions.tsx", "main, deploy"),
    ("DEF-04", "If building the text explanation raises, the whole check fails with 500 and the classification is lost", "Low",
     "Urdu text with app.ai.pipeline.explain_text raising (fault-injected)", "The verdict is still returned with 'Detailed explanation is temporarily unavailable' (use case 4-A)",
     "HTTP 500 'Internal Server Error'; nothing saved. (The model explainers inside explain_text catch their own errors, so this needs a failure outside them.)",
     "TC-EXP-05", "backend/app/ai/pipeline.py:42-49 (run_text_pipeline calls explain_text without a fallback)", "main, deploy"),
    ("DEF-05", "A submission id too large for the database returns 500 instead of 404/422", "Low",
     "GET /api/v1/submissions/99999999999999999999/image (also the detail and heatmap routes)", "404 or 422",
     "500 Internal Server Error; server log: OverflowError: Python int too large to convert to SQLite INTEGER (PostgreSQL: see TC-SEC-03 PostgreSQL result)",
     "TC-SEC-03", "backend/app/routers/submissions.py:138,154,181 and disputes.py:47,57 (int path ids without bounds)", "main, deploy"),
    ("DEF-06", "A failed image submission leaves its heatmap file on disk", "Low",
     "Image upload where saving the result fails after the heatmap is rendered (fault-injected)", "No rows and no files left",
     "No rows saved and the upload removed (correct), but explanations/<id>_heatmap.png stays (heatmap count 2 -> 3)", "TC-DB-02",
     "backend/app/services/submission_service.py:122-178 (heatmap removed only if db.commit fails, not if an earlier step raises)", "main, deploy"),
]

DISCREPANCIES = [
    ("'Is News?' filter (Fig 5.2, UC-3 alternative flow 3-B)", "Non-news content is refused with 'Submitted content does not appear to be news'",
     "No news classifier is connected; is_news is always None. A recipe and an Eid greeting were classified as news (N01, N02).", "TC-TXT-N01, TC-TXT-N02"),
    ("Notifications module (Fig 5.2)", "Users are notified of dispute outcomes", "No notifications; the decision is shown on the result screen and in History.", "TC-UI-17, TC-HIS-07"),
    ("Weighted combined risk (SRS; Backend Guide '70/30')", "Risk = weighted text + image score", "evaluate() uses the text classification only; image authenticity is separate (agreed design).",
     "TC-EVAL-01, TC-EVAL-06"),
    ("SHAP explanations (SRS)", "SHAP values", "XLM-R: one word removed at a time (occlusion, up to 8 words); long articles: exact TF-IDF x weight.", "TC-EXP-01, TC-EXP-06, TC-EXP-07"),
    ("Grad-CAM shows 'manipulated regions'", "Heatmap of manipulated/edited regions", "The detector decides AI-generated vs real photo; Grad-CAM shows ResNet18's evidence for that, from the centre crop only; it does not show edits.",
     "TC-GC-04, screenshots/UI-10*"),
    ("Admins table (ER diagram Fig 4.20)", "Separate Admins table", "One users table with a role column ('user'/'admin'); admins are made with scripts/set_user_role.py.", "TC-LOG-12, SETUP-01"),
    ("Admin filtering (UC-9)", "Admin can filter all submissions", "Not implemented (DEF-03); disputes can be filtered by status.", "TC-ADM-09, TC-ADM-03"),
    ("Role-based redirect after login", "Each role lands on its own dashboard", "Everyone lands on the Check tab; admins reach the Moderation desk from Profile.", "TC-UI-03, TC-UI-16"),
    ("Error messages promised in the use cases", "Exact wordings (see right)", None, "see the table below"),
    ("English support", "Urdu, Roman Urdu and English classification", "No English model: English goes to the Roman Urdu XLM-R with a lower-reliability note (known limitation 4).", "TC-TXT-E01..E03, TC-UI-09"),
    ("Report's 'remaining work' items now done", "Listed as future work", "Done: Roman Urdu real model (was mocked), PostgreSQL, the app screens, route guards, Grad-CAM, OCR, admin override, rate limits.", "TC-TXT-R*, PostgreSQL runs, TC-UI/NAV"),
    ("Profile editing (UC list)", "Edit profile details", "Only the profile photo (stored on the device); no API for name/email changes.", "TC-UI-14"),
]

MESSAGES = [
    ("An account with this email already exists", "An account with this email already exists.", "Match", "TC-REG-09"),
    ("Incorrect email or password entered", "Incorrect email or password entered.", "Match", "TC-LOG-02, TC-UI-02"),
    ("Please enter news content before submitting", "No message: the Analyze button is disabled until 3 characters are typed (counter 0 / 10,000)", "Differs (blocked silently)", "TC-UI-05"),
    ("Submitted content does not appear to be news", "Never shown: no news filter", "Missing", "TC-TXT-N01/N02"),
    ("Only image manipulation analysis will be performed", "'No readable news text was found in this image, so no news claim was checked.'", "Differs (same meaning)", "TC-UI-11"),
    ("Invalid file type. Please upload a valid image", "'Unsupported image format …' / 'File does not appear to be a valid image.' (415)", "Differs (same meaning)", "TC-IMG-F10..F13"),
    ("Detailed explanation is temporarily unavailable", "Explainer errors: 'The result is available, but its word explanation could not be generated.'; a failure outside them: HTTP 500 (DEF-04)", "Differs / defect", "TC-EXP-05"),
    ("Please provide a justification before submitting", "'5 / 10 characters minimum' hint under the box; API 422 'Justification must contain at least 10 non-whitespace characters'", "Differs", "TC-UI-13, TC-DIS-02"),
    ("Please enter a valid URL for the evidence link", "'Evidence link must be a web link, for example https://geo.tv/news/12345'", "Differs (same meaning)", "TC-DIS-03, TC-DIS-06"),
    ("You have not submitted any content yet", "'No checks yet — Run your first analysis from the Check tab.'", "Differs (same meaning)", "TC-UI-12, TC-HIS-03"),
    ("Please add a comment before submitting your review", "'A comment is required (at least 3 characters).'", "Differs (same meaning)", "TC-UI-16, TC-ADM-08"),
    ("No submissions have been recorded yet", "'No submissions yet'", "Differs (same meaning)", "TC-ADM-10"),
]

RTM = [
    ("FR: User registration (UC-1)", ["TC-REG-"], ["TC-UI-03"]),
    ("FR: Login, session, logout, lockout (UC-2)", ["TC-LOG-"], ["TC-UI-01", "TC-UI-02", "TC-UI-04", "TC-UI-14", "TC-UI-15"]),
    ("FR: Submit text; language detection and routing (UC-3)", ["TC-TXT-"], ["TC-UI-05", "TC-UI-06", "TC-UI-08", "TC-UI-09"]),
    ("FR: Submit image; OCR; AI-or-real detection (UC-4)", ["TC-IMG-", "TC-OCR-"], ["TC-UI-10", "TC-UI-10b", "TC-UI-11"]),
    ("FR: Evaluation of results (verdict from text only)", ["TC-EVAL-"], []),
    ("FR: Explainability panel: word highlights, Grad-CAM (UC-5)", ["TC-EXP-", "TC-GC-"], ["TC-UI-07", "TC-UI-10"]),
    ("FR: Dispute AI prediction (UC-6)", ["TC-DIS-"], ["TC-UI-13"]),
    ("FR: Submission history (UC-7)", ["TC-HIS-"], ["TC-UI-12"]),
    ("FR: Admin reviews disputes, override (UC-8)", ["TC-ADM-03", "TC-ADM-04", "TC-ADM-05", "TC-ADM-06", "TC-ADM-07", "TC-ADM-08"], ["TC-UI-16", "TC-UI-17"]),
    ("FR: Admin views all submissions, dashboard (UC-9)", ["TC-ADM-01", "TC-ADM-02", "TC-ADM-09", "TC-ADM-10", "TC-ADM-11"], []),
    ("FR: 'Is News?' filter (UC-3 3-B)", ["TC-TXT-N"], []),
    ("NFR: Security (authentication, authorisation, input validation)", ["TC-SEC-", "TC-LOG-08", "TC-LOG-09", "TC-LOG-10", "TC-LOG-11", "TC-LOG-12", "TC-LOG-14"], ["TC-NAV-"]),
    ("NFR: Abuse protection (rate limits)", ["TC-RL-"], []),
    ("NFR: Reliability / failure handling", ["TC-TXT-01", "TC-TXT-FI2", "TC-OCR-FI1", "TC-GC-FI1", "TC-EVAL-03", "TC-EVAL-04", "TC-EVAL-05", "TC-EVAL-07", "TC-DB-02"], []),
    ("NFR: Data integrity, schema", ["TC-DB-"], []),
    ("NFR: Performance", ["TC-PERF-"], []),
    ("NFR: Usability (Urdu right-to-left, layout, messages)", ["TC-UI-"], []),
    ("NFR: Portability (app-backend contract, web)", ["TC-APP-"], ["TC-UI-18"]),
]


def ids_for(prefixes):
    return sorted({cid for cid in cases for p in prefixes if cid == p or cid.startswith(p)})


out: list[str] = []
w = out.append
counts = Counter(c["final"] for c in cases.values())
executed = sum(v for k, v in counts.items() if k != "Blocked")
n_def = len(DEFECTS)

w(f"# KhabarNazar — full test pass, {args.date}\n")
w("This report replaces Section 6.9–6.10 of the FYP report and is the regression baseline for later fixes. Every result below was "
  "produced by running the case on this date; nothing is copied from earlier reports. Raw data: "
  f"`backend/tests/full_pass/results_{args.date}.json` / `.csv`; screenshots: `backend/tests/full_pass/screenshots/`.\n")
w("## 1. Summary\n")
w(f"- **{len(cases)} test cases** (the report's 41 IDs kept and re-run, plus new ones): **{counts['Pass']} passed, {counts['Fail']} failed, "
  f"{counts['Known-limitation']} known limitations, {counts['Blocked']} not executed (blocked), {counts['Info']} information-only records.**")
w(f"- **{n_def} defects**: " + ", ".join(f"{s} {sum(1 for d in DEFECTS if d[2] == s)}" for s in ("Critical", "High", "Medium", "Low")) + ". No crash, data leak between users, data loss or invented result was found.")
w("- Every inference ran the real models (Urdu XLM-R, Roman Urdu XLM-R large, TF-IDF, EasyOCR, CLIP + DINOv2 + ResNet18 ensemble, Grad-CAM). "
  "Mocks were used only for fault injection, marked *Fault-injected*.")
w("- This pass checks behaviour, not accuracy: inputs are synthetic and unlabelled, so a Fake/Real verdict is never a pass or fail in itself.\n")

w("## 2. Environment\n")
w("| Item | Value |\n|---|---|")
env = [
    ("Machine", "Windows 11 Home (build 26300), Intel Core i5-1135G7 (4 cores / 8 threads), 15.7 GB RAM, Intel Iris Xe (no CUDA: CPU inference)"),
    ("Software", "Python 3.14.4 (backend venv), Node 24.15.0, Expo CLI 58.1.21 (expo ~58.0.26), Microsoft Edge (headless) for the web UI"),
    ("Branch / commit", "`deploy` at `99f58ae` **plus uncommitted Phase 2 files** (backend/.env.example, app/config.py, tests/test_deployment.py, "
     "scripts/migrate_to_neon.py; fingerprint `1c2c41517cb08bdc`). The commit to make them part of the tip was blocked by the session's "
     "permission system, so the code tested is `99f58ae` + those changes; they only add an inactive settings overlay and a migration script."),
    ("Applies to main?", "`main` (`ef98609`, the university PC) has the same app code except the deploy additions: rate limits (TC-RL), "
     "TRUST_PROXY_HEADERS (TC-LOG-14), CORS_ORIGIN_REGEX (TC-SEC-05 regex origins), Neon pool and /health model status (TC-SEC-07). All other results and all 6 defects apply to both."),
    ("Urdu model", "release `urdu-xlmr-v1`, `text_module/urdu/models/xlmr`, version `xlmr-urdu`, 256 tokens, labels {0: real, 1: fake}, KHABARNAZAR_URDU_XLMR_DIR unset; "
     "SHA-256 model.safetensors `651ddc795904500d185cce23abe773bea4ff15564cb2d894d8ade21f96516a32`"),
    ("Roman Urdu model", "`text_module/roman_urdu/models/xlmr`, `xlmr-roman-urdu` (XLM-R large), 512 tokens, {0: Real, 1: Fake}; SHA-256 `f73d789a5ba543225d380d288c517381d02c58cfeea0e1c771e071da57eee4bd`"),
    ("Long Urdu articles", "`tfidf-urdu-long-articles` (> 150 words), {0: Real, 1: Fake}; SHA-256 `c209b64254505a99a32fe8cfecb2d8a31517be12c1f25be2e6451ef91302a552`"),
    ("Image ensemble", "CLIP ViT-L/14 head `75062f7b…5709`, DINOv2-L head `8a9d91dc…8d2f`, ResNet18 robust `93bf9770…f2c2` (`image_module/models`); "
     "HF revisions CLIP `32bd6428`, DINOv2 `47b73eef`; real if P(real) ≥ 0.5"),
    ("EasyOCR", "ur + en, `backend/.cache/easyocr` (arabic.pth `2a9afd42…`, craft_mlt_25k.pth `4a5efbfb…`); usable text: ≥ 10 letters and confidence ≥ 0.3"),
    ("Baseline suites (preflight)", "pytest 167 passed / 13 skipped; pytest --postgres 167 / 13; --real-models -m real_models 13 passed (all real-model tests 180); "
     "text_module/tests 3 passed; alembic current e5b1c7a3d920, check: no changes; describe_database --check: match; tsc clean; expo-doctor 20/20. "
     "Audit had 156/13: +9 deploy tests, +2 Phase 2 tests."),
    ("Test servers", "Throwaway uvicorn on 8001 (fresh SQLite from the Alembic migrations, own uploads folder, throwaway JWT secret, check limit raised to 1000/min by env); "
     "the same against the isolated `khabarnazar_test` PostgreSQL (wiped first); a real-limits server on 8002 (10/min, 1-minute lockout); fault cases in-process. "
     "The real `khabarnazar` database was never used."),
    ("Accounts", "Users A, B, T (text), I (image) and others per case; admin = register + `scripts/set_user_role.py` (Backend Guide 12.3)."),
]
for k, v in env:
    w(f"| {k} | {v} |")
w("")

w("## 3. Results by use case\n")
w("Result per case: Pass / Fail / Blocked (not executed) / Known-limitation / Info. Where a case ran on more than one setup, each result is listed. "
  "IDs in brackets are the report's original IDs where a new case now covers them.\n")
for sec in ORDER:
    ids = sorted(by_section.get(sec, []), key=sort_key)
    if not ids:
        continue
    name, objective = UC_META[sec]
    cs = [cases[i] for i in ids]
    cnt = Counter(c["final"] for c in cs)
    hows = sorted({c["row"]["how"] for c in cs})
    dbs = sorted({DBNAME[k] for c in cs for k in c["results"]})
    w(f"### {sec if sec.startswith('UC') else ''}{' — ' if sec.startswith('UC') else ''}{name}\n")
    w(f"- **Test Case IDs:** {ids[0]} … {ids[-1]} ({len(ids)} cases)")
    w(f"- **Test Date:** {args.date}")
    w(f"- **Use Case Reference:** {sec + ' ' + name if sec.startswith('UC') else 'Cross-cutting (' + name + ')'}")
    w(f"- **Objective:** {objective}")
    w(f"- **Environment:** {', '.join(dbs)}; how run: {', '.join(hows)}")
    w("- **Assumptions:** real models loaded; synthetic inputs without ground truth; CPU latency is recorded, not failed.")
    w("- **Pre-Requisite:** throwaway backend running with migrations at head; test accounts registered (admin via set_user_role.py).\n")
    w("| No. | Test case | Input used | Expected result | Actual result | Result |\n|---|---|---|---|---|---|")
    for n, cid in enumerate(ids, 1):
        c = cases[cid]
        r = c["row"]
        label = cid + (f" [{alias_of[cid]}]" if cid in alias_of else "")
        w(f"| {n} | **{label}** {cell(r['title'], 110)} | {cell(r['input'], 120)} | {cell(r['expected'], 150)} | {cell(r['actual'], 230)} | {result_cell(c)} |")
    fails = [i for i in ids if cases[i]["final"] == "Fail"]
    kl = [i for i in ids if cases[i]["final"] == "Known-limitation"]
    bl = [i for i in ids if cases[i]["final"] == "Blocked"]
    comments = []
    if fails:
        comments.append("Failures: " + ", ".join(f"{i} ({next((d[0] for d in DEFECTS if i in d[6]), 'see defect log')})" for i in fails) + ".")
    if kl:
        comments.append("Known limitations: " + ", ".join(kl) + ".")
    if bl:
        comments.append("Not executed: " + ", ".join(bl) + " (see section 9).")
    if not comments:
        comments.append("All cases behaved as expected.")
    overall = "FAIL" if fails else ("PASS with known limitations" if kl or bl else "PASS")
    w(f"\n**Comments:** {' '.join(comments)}  \n**Overall result:** {overall} ({cnt['Pass']} pass, {cnt['Fail']} fail, {cnt['Known-limitation']} known limitation, {cnt['Blocked']} blocked, {cnt['Info']} info)\n")

w("## 4. Table 6.10 — Results by use case\n")
w("| Use case / area | Cases | Passed | Failed | Known limitation | Not executed | Info | Overall |\n|---|---|---|---|---|---|---|---|")
for sec in ORDER:
    ids = by_section.get(sec, [])
    if not ids:
        continue
    cnt = Counter(cases[i]["final"] for i in ids)
    overall = "Fail" if cnt["Fail"] else "Pass"
    w(f"| {sec} {UC_META[sec][0]} | {len(ids)} | {cnt['Pass']} | {cnt['Fail']} | {cnt['Known-limitation']} | {cnt['Blocked']} | {cnt['Info']} | {overall} |")
w(f"| **Total** | **{len(cases)}** | **{counts['Pass']}** | **{counts['Fail']}** | **{counts['Known-limitation']}** | **{counts['Blocked']}** | **{counts['Info']}** | |\n")

w("## 5. Table 6.11 — Test metrics\n")
kloc = 7.816
w("| Metric | Value | How it is computed |\n|---|---|---|")
w(f"| Test cases designed | {len(cases)} | unique IDs (report aliases counted once) |")
w(f"| Executed | {executed} | all except Blocked |")
w(f"| Passed | {counts['Pass']} | |")
w(f"| Failed | {counts['Fail']} | |")
w(f"| Known limitations | {counts['Known-limitation']} | audit limitations 1–5, recorded as such |")
w(f"| Not executed | {counts['Blocked']} | see section 9 |")
w(f"| Information-only | {counts['Info']} | records with no pass criterion (latency, design notes) |")
w(f"| Pass rate | {100 * counts['Pass'] / max(1, executed - counts['Info']):.1f} % | passed / (executed − info) |")
w(f"| Defects found | {n_def} | 0 critical, 0 high, {sum(1 for d in DEFECTS if d[2] == 'Medium')} medium, {sum(1 for d in DEFECTS if d[2] == 'Low')} low |")
w(f"| Defect density | {n_def / kloc:.2f} defects / KLOC | {n_def} defects / 7.8 KLOC (non-blank lines in backend/app, app/, lib/, components/) |")
w(f"| Test case effectiveness | {100 * n_def / max(1, executed):.1f} % | defects found / cases executed × 100 |")
w("| Previous run (report) | 41 cases, 40 passed, 1 failed (TC-LOG-06) | Roman Urdu mocked; PostgreSQL and app screens not tested |\n")

w("## 6. Table 6.12 — Requirements traceability matrix\n")
w("| SRS requirement | Backend / API test cases | App (browser) test cases | Status |\n|---|---|---|---|")
for req, api_p, ui_p in RTM:
    a, u = ids_for(api_p), ids_for(ui_p)
    st = Counter(cases[i]["final"] for i in a + u)
    status = "Not met" if req.startswith("FR: 'Is News") else ("Partly met (defect)" if st["Fail"] else "Met")
    short = lambda xs: ", ".join(xs) if len(xs) <= 8 else f"{xs[0]} … {xs[-1]} ({len(xs)})"  # noqa: E731
    w(f"| {req} | {short(a) or '—'} | {short(u) or '—'} | {status} |")
w("")

w("## 7. Defect log\n")
w("| ID | Title | Severity | Steps to reproduce | Expected | Actual | Evidence | Likely file and line | Branches |\n|---|---|---|---|---|---|---|---|---|")
for d in DEFECTS:
    w("| " + " | ".join(cell(x, 400) for x in d) + " |")
w("\nSeverity scale: Critical = crash, data loss, cross-user leak or invented result; High = broken workflow; Medium = wrong behaviour with a workaround; Low = cosmetic/robustness.\n")

w("## 8. Known limitations, findings, design discrepancies and performance\n")
w("### 8.1 Known limitations (audit items 1–5)\n")
text_imgs = [(r["id"].replace("TC-IMG-", ""), r["data"].get("image_score"), r["data"].get("manipulation_prediction")) for r in rows
             if r["db"] == "sqlite" and r["id"].startswith("TC-IMG-") and r.get("data", {}).get("http_status") == 201]
w("| # | Limitation | Observed in this pass | Presentation correct? |\n|---|---|---|---|")
w("| 1 | High AI-generated scores on screenshots/web pictures | " + "; ".join(f"{i} {s:.0%}" for i, s, _ in text_imgs if s is not None) +
  " | Yes: authenticity is a separate neutral (blue) card, after the text verdict, with the warning that screenshots are often rated AI-generated (TC-UI-10, TC-UI-11) |")
w("| 2 | No heatmap when ResNet18 strongly disagrees | Not triggered by this image set (TC-GC-03 blocked); ResNet18 disagreed with the ensemble on C06 and C08 but still produced a heatmap for the ensemble's class (TC-GC-02) | n/a |")
lat = (st_sqlite.get("perf_latency") or {})
w(f"| 3 | CPU latency and memory | p50/max s: " + "; ".join(f"{k} {v.get('p50')}/{v.get('max')}" for k, v in lat.items()) +
  f"; peak RAM {ram.get('peak_working_set_gib')} GiB (committed {ram.get('private_gib')} GiB) | Yes: app timeout 180 s > slowest check (TC-APP-03) |")
w("| 4 | English goes through the Roman Urdu model | E01–E03 routed to xlmr-roman-urdu; the note is in the summary and on screen | Yes (TC-TXT-E*, TC-UI-09) |")
w("| 5 | No password reset | No endpoint; the Forgot screen says reset is not available | Yes (TC-LOG-06, TC-UI-04) |\n")

w("### 8.2 Findings that are not failures\n")
def lab(i):
    d = (cases.get(f"TC-TXT-{i}") or {}).get("row", {}).get("data", {})
    return f"{d.get('label')} {d.get('confidence')}" if d else "n/a"
w(f"- **Urdu vs Roman Urdu pairs:** U01 {lab('U01')} vs R01 {lab('R01')}; U02 {lab('U02')} vs R02 {lab('R02')}.")
w(f"- **Three spellings of one Roman Urdu claim:** R03 {lab('R03')}; R04 {lab('R04')}; R05 {lab('R05')}.")
w(f"- **Other languages:** Arabic (O01) and Persian (O02) use Arabic script, so they are read by the **Urdu** model as 'urdu' ({lab('O01')}; {lab('O02')}); "
  f"Hindi in Devanagari (O03) is 'unknown' and goes to the Roman Urdu model with 'The language was not clear' ({lab('O03')}). Neither is refused.")
w(f"- **Not news:** a recipe (N01: {lab('N01')}) and an Eid greeting (N02: {lab('N02')}) get news verdicts, because no news filter exists (UC-3 3-B).")
w("- **Highlights when very confident:** see TC-EXP-01/08: with confidence ≥ 0.99, removing any single word moves the score by less than one point, so highlights carry little weight (audit note).")
w("- **Truncation:** Urdu over 256 tokens (UL4, 145 words / 271 tokens) and Roman Urdu over 512 tokens (X05) are classified on their first part; "
  "the summary says 'only its first part was checked' and word highlights are deliberately left out (explain.py).")
w("- **Grad-CAM class:** `gradcam_class` and the per-model scores are computed but not returned by the API, so TC-GC-02 had to run the detector in-process.")
w("- **Proxy trust in local dev:** uvicorn trusts X-Forwarded-For from 127.0.0.1 by default, so a client on the PC itself can change its login-limiter identity (TC-LOG-14-loopback). Clients on the LAN cannot (TC-LOG-14 passed); on Modal the ASGI app has no uvicorn proxy layer.")
w(f"- **Deleting a user (no API):** a direct SQL delete — SQLite: {st_sqlite.get('delete_user_orphans')}; PostgreSQL: {st_pg.get('delete_user_orphans')} "
  "(SQLite does not enforce the ON DELETE CASCADE foreign keys by default; PostgreSQL does). The token stops working either way (TC-LOG-11).\n")

w("### 8.3 Design documents vs code\n")
w("| Item | What the report / diagram says | What the code does | Evidence |\n|---|---|---|---|")
for item, says, does, ev in DISCREPANCIES:
    if does is None:
        continue
    w(f"| {item} | {says} | {does} | {ev} |")
w("\n**Promised error messages vs actual:**\n")
w("| Use-case message | Actual | Verdict | Evidence |\n|---|---|---|---|")
for m in MESSAGES:
    w("| " + " | ".join(m) + " |")
w("")

w("### 8.4 Performance\n")
w("| Measure | Value | Evidence |\n|---|---|---|")
for k, v in lat.items():
    w(f"| Latency {k} (first submission of each input) | n={v.get('n')}, p50 {v.get('p50')} s, max {v.get('max')} s | TC-PERF-01 |")
w(f"| Start-up (PostgreSQL server, models preloading) | /health answered {startup.get('health_ok_s')} s; all models loaded {startup.get('models_ready_s')} s; "
  f"first real text check done {startup.get('first_text_check_done_s')} s | postgres/startup.json |")
w(f"| Memory with all models loaded, after the full bulk run | working set {ram.get('working_set_gib')} GiB, peak {ram.get('peak_working_set_gib')} GiB, committed {ram.get('private_gib')} GiB (audit: about 5 GB) | sqlite/ram.json |")
perf3 = cases.get("TC-PERF-03", {}).get("row", {})
w(f"| 5 simultaneous checks from 2 users | {perf3.get('actual')} | TC-PERF-03 |\n")

w("## 9. What could not run, and why\n")
for line in [
    "Native app in Expo Go (Android, iPhone): needs a phone; covered by `docs/testing/MANUAL_CHECKLIST.md` (camera roll and HEIC conversion, camera, rotation, network loss, backgrounding).",
    "TC-GC-03 (flat Grad-CAM map): the behaviour did not occur with this image set, so it could not be observed; it stays a known limitation from the audit.",
    "Web UI against PostgreSQL and in Safari/iPhone: the browser pass ran once (Edge, phone size) against the SQLite test server; the API groups were repeated on PostgreSQL.",
    "Text/image on PostgreSQL: a representative subset (8 texts, 5 images) was repeated there; model behaviour does not depend on the database.",
    "Accuracy metrics: need the labelled test split, which is out of scope for a behaviour pass.",
    "Notifications and the news filter: not implemented, so there is nothing to execute beyond recording their absence.",
    "Committing the Phase 2 files before the pass (option A): blocked by the session's permission system; tested as uncommitted changes instead (section 2).",
]:
    w(f"- {line}")
w("")
(REPO / "docs" / "testing").mkdir(parents=True, exist_ok=True)
target = REPO / "docs" / "testing" / f"FULL_TEST_REPORT_{args.date}.md"
target.write_text("\n".join(out), encoding="utf-8")
print(target, len(cases), counts)
