# Text module test results: TC-TXT-01 to TC-TXT-39 (2026-11-28)

The text test cases from the test case sheet were run against the real backend with the real models.
Raw responses: `backend/tests/text_cases/results_2026-11-28.json`. Sheet columns E/F:
`backend/tests/text_cases/results_2026-11-28.csv`. Inputs: `backend/tests/text_cases/inputs.json`.
Screenshots: `backend/tests/text_cases/screens/`. This was a testing-only pass: no application code, model,
checkpoint, label map, preprocessing or threshold was changed.

## 1. Environment

| Item | Value |
|---|---|
| Machine | HP Laptop 14-dq2xxx, Intel Core i5-1135G7 @ 2.40 GHz, 16 GB RAM, Windows 11 Home, CPU only |
| Software | Python 3.14.4, torch 2.14.1+cpu, transformers 5.20.2, Expo web (SDK 58), headless Microsoft Edge |
| Branch / commit | Checked out: `main` at `0087378` (clean apart from the empty untracked `backend/models/`). `deploy` tip is `a623335`. `git diff deploy main -- backend text_module` (tests excluded) is **empty**, so the backend and models tested are exactly the `deploy` tip. The web build differs from `deploy` only in the role-based redirect, admin header and the Check screen info card, none of which is on the text check path. |
| Backend under test | Separate uvicorn on port 8001 (`tests/full_pass/start_test_server.py`), throwaway SQLite database built by the Alembic migrations (head `e5b1c7a3d920`), its own uploads folder, all models preloaded. The real PostgreSQL `khabarnazar` database was not used. The developer backend on port 8000 was stopped during the run to free RAM, then restarted. |
| Urdu model | Release `urdu-xlmr-v1`: `text_module/urdu/models/xlmr`, version `xlmr-urdu`, 256 tokens, labels {0: real, 1: fake}, no `khabarnazar_config.json` (notebook checkpoint, `clean_urdu_notebook`). `KHABARNAZAR_URDU_XLMR_DIR` is not set (process, user and machine environment, and `backend/.env`). `text-model-v1` (`models/text/xlmr`) is present on disk but is **not** loaded. SHA-256 `model.safetensors` `651ddc795904500d185cce23abe773bea4ff15564cb2d894d8ade21f96516a32`, `tokenizer.json` `1d237c4974cfea16dffbc5035028fea5b47ad8b653af90c908b7a35bdc8b0d90` |
| Roman Urdu model | `roman-urdu-xlmr-v1`: `text_module/roman_urdu/models/xlmr`, version `xlmr-roman-urdu`, 512 tokens, labels {0: Real, 1: Fake}. SHA-256 `model.safetensors` `f73d789a5ba543225d380d288c517381d02c58cfeea0e1c771e071da57eee4bd`, `tokenizer.json` `d1065c14bf5f3d26a369bb348eae791e137f4b69cc85f846cc14bde0e6c49aca` |
| Long-article model | `text_module/urdu/models/tfidf_long_articles.joblib`, version `tfidf-urdu-long-articles`, SHA-256 `c209b64254505a99a32fe8cfecb2d8a31517be12c1f25be2e6451ef91302a552` |

### Preflight values found in the code

| Setting | Value and where |
|---|---|
| Long-article cutoff | `LONG_TEXT_WORDS = 150` (`app/config.py`, env `KHABARNAZAR_LONG_TEXT_WORDS`). Urdu text with **more than** 150 whitespace-separated words (`len(text.split()) > 150`, `app/ai/text/long_articles.py`) goes to the TF-IDF model; 150 or fewer go to Urdu XLM-R. Roman Urdu has no long-text route. |
| Text length | `TextSubmitRequest.text`: `min_length=3`, `max_length=10_000` on the raw string, then a validator strips it and requires at least 3 non-space characters (`app/schemas/submission.py`). The stripped text is what is stored. |
| No letters → Uncertain | `model_language()` in `app/ai/text/predict.py`: links and email addresses are removed, then if no character is `str.isalpha()`, no model runs and the result is Uncertain with no score, model version `text-model-unavailable`, summary “The text has no words to classify (only links, numbers or symbols).” |
| Rate limit | `CHECK_RATE_LIMIT_PER_MINUTE = 10`, `CHECK_RATE_LIMIT_PER_HOUR = 100` (`app/config.py`; env vars of the same names; 0 turns a limit off). Per signed-in user, in memory, sliding window, on both check endpoints (`app/utils/rate_limit.py`); over the limit → 429 with `Retry-After`. The main run raised them (1000/min, 100000/h) through these env vars only; TC-TXT-34 ran on a fresh server with the real values. |
| App request timeout | `ANALYSIS_TIMEOUT_MS = 180_000` (180 s) in `lib/api.ts` for text and image checks. The runner used the same 180 s. |

How the cases ran: `run_text_cases.py` calls the API as `lib/api.ts` does (`POST /api/v1/submissions/text`
`{"text": …}` with a Bearer token, `GET /api/v1/submissions/{id}`, `GET /api/v1/submissions?skip=&limit=`) with
two registered users A and B. TC-TXT-01 and TC-TXT-31 are the only fault-injected cases. They ran in a child
test process (FastAPI TestClient on the same SQLite database with user A's token): TC-TXT-01 set
`KHABARNAZAR_URDU_XLMR_DIR` to an empty temporary folder, and TC-TXT-31 monkeypatched XLM-R inference to raise once.
No model file was renamed or deleted. TC-TXT-34 ran on a second fresh throwaway server with the real limit,
so users A and B were registered again there. The web cases (`web_text_cases.py`) drove headless Edge at phone size
(390×844) against Expo web on port 8082, with `EXPO_PUBLIC_API_URL` set to the test backend.

## 2. Totals

| Result | Count | Cases |
|---|---|---|
| Pass | 30 | 01–10, 14–17, 22–31, 33–35, 37–39 |
| Fail | 0 | none |
| Finding | 8 | 11, 12, 18, 19, 20, 21, 32, 36 |
| Known limitation | 1 | 13 |
| Not run | 0 | none |

All 39 cases ran. TC-TXT-37 is a Pass with an extra observation (F9 below).

## 3. Failures

None. No case met the Fail condition: no crash, no 5xx, no wrong route, no invented score and no data leak.

## 4. Findings

| # | Case | Finding | Evidence | Suggested severity | Likely file |
|---|---|---|---|---|---|
| F1 | TC-TXT-11 | Spelling variants of the same Roman Urdu claim get opposite labels | “Hukoomat ne petrol 5 rupay sasta kar diya hai” Fake 0.9966; “Hakumat ne petrol 5 rupe sasta kr dia he” **Real 0.7919**; “Hkumat ne petrol 5 rs sasta kar dya hai” Fake 0.9985 (all `xlmr-roman-urdu`) | Medium (model robustness) | `text_module/roman_urdu` model; no normalisation in `app/ai/text/xlmr.py` `prepare()` for Roman Urdu |
| F2 | TC-TXT-12 | The same claim in Urdu script and in Roman Urdu can get opposite labels | 02 Urdu Real 0.9984 vs 04 Roman Real 0.9794 (agree). 07 Urdu **Fake 0.9994** vs 08 Roman **Real 0.995** (internet shutdown claim) | Medium (model consistency) | the two separately trained checkpoints |
| F3 | TC-TXT-18 | Arabic is detected as “urdu” and classified by the Urdu model with high confidence | `urdu · xlmr-urdu · Real 0.9998` | Low–Medium | `app/ai/text/language_detection.py` (any Arabic-script letter counts as Urdu) |
| F4 | TC-TXT-19 | Persian is detected as “urdu” and classified by the Urdu model with high confidence | `urdu · xlmr-urdu · Real 0.9998` | Low–Medium | `app/ai/text/language_detection.py` |
| F5 | TC-TXT-20 | Hindi (Devanagari) is checked by the Roman Urdu model and gets a confident label. The summary says “The language was not clear, so the text was checked as Roman Urdu.” | `unknown · xlmr-roman-urdu · Fake 0.9878` | Low–Medium | `app/ai/text/predict.py` `model_language()` (any non-Arabic letters go to Roman Urdu) |
| F6 | TC-TXT-21 | Non-news text gets a news verdict. The use case expects “Submitted content does not appear to be news”, but no news filter is connected (`is_news` is null) | recipe text → `urdu · xlmr-urdu · Real 0.9997`, `is_news=None` | Medium (use-case gap) | `app/ai/pipeline.py` / `SubmissionResponse.is_news` (no classifier) |
| F7 | TC-TXT-32 | The history list response has no language field. Label, order and filtering are correct, but the language is only in the full record | 34 items, newest first, label on each, `detected_language` absent from `GET /submissions` items (present in 34/34 full records); none of the TC-TXT-05 inputs saved | Low | `app/schemas/submission.py` `SubmissionListItem` |
| F8 | TC-TXT-36 | An empty box sends no request because Analyze is disabled (`aria-disabled=true`), but no message appears. The use case's “Please enter news content before submitting” is never shown | 0 requests, history unchanged, no dialog or text | Low (UX wording) | `app/(tabs)/index.tsx` (`MIN_TEXT`, disabled button) |
| F9 | TC-TXT-37 (Pass) | The User claim card on the result screen shows only the first 280 characters. It is cut mid-word with no ellipsis or “show more” | 200-word article ends “…غیر ضروری س” on the result screen (`TC-TXT-37_long_urdu_result_scrolled.png`) | Low | `lib/SubmissionsContext.tsx` (`textPreview: text.slice(0, 280)`) |

Other observations (no result changed):

- TC-TXT-22: `"abc"` is checked by the Roman Urdu model as “language not clear” and gets Real 0.9257. This is the
  same behaviour as F5, for a three-letter non-word.
- TC-TXT-10: the 135-word, 292-token Urdu text is classified by `xlmr-urdu` after truncation to 256 tokens, and the
  summary says “The text is long, so only its first part was checked.” No word highlights are returned for
  truncated input. This is by design (`app/ai/text/explain.py`).
- TC-TXT-27: zero-width spaces and double spaces made no difference: same route, label and confidence as TC-TXT-04.
- TC-TXT-26: mixed `<script>`+Urdu text is detected as “mixed” and routed to `xlmr-urdu`. It is stored byte-for-byte
  as sent, shown as plain text on the result, Check and History screens, and no alert fired.
- The highlight-weight Known limitation did not occur. The 02, 03 and 04 highlights all had clear weights:
  max |weight| 0.97, 0.20 and 0.11. This limitation is not itself listed in `DEVELOPMENT_READINESS_AUDIT.md`. The
  audit lists English routing and CPU latency.

Known limitation: TC-TXT-13 (English). It goes to `xlmr-roman-urdu` (Real 0.5662), and the summary says results for
English are less reliable, as audit §15 #7 describes.

## 5. Latency per model (client-measured, includes the word explanation)

| Model | Checks | Median | Max |
|---|---|---|---|
| `xlmr-urdu` | 12 | 0.6 s | 2.2 s |
| `tfidf-urdu-long-articles` | 3 | 1.3 s | 2.6 s |
| `xlmr-roman-urdu` | 13 | 5.1 s | 10.5 s |
| no model (no letters) | 3 | 0.01 s | 0.01 s |

The web Roman Urdu check (TC-TXT-38) took 9.8 s from tap to result, well inside the app's 180 s timeout.
TC-TXT-31's 14.8 s includes loading the Urdu model into the fault-injection test process, so it is excluded above.

## 6. Per-case results

See `results_2026-11-28.csv` for the one-line evidence per case. In summary:

- Routing, validation and auth: 02–10, 14–17, 22–25, 33 Pass.
- Fault handling: 01 Pass (unavailable model → Uncertain, saved, no score). 31 Pass (inference error logged,
  Uncertain, no score, and the same process served the next check normally).
- Determinism: 28 Pass (identical label, confidence and highlights over three submissions each).
- Risk: 29 Pass. Risk equals P(fake) for all 29 classified results. Confident Real has risk ≤ 0.0743 and
  confident Fake has risk ≥ 0.981.
- Rate limit: 34 Pass. 10×201, then 429 at 4.2 s: “Too many checks in a short time. Please try again in 56
  seconds.” with `Retry-After: 56`. User B was unaffected.
- Web: 26, 35, 37, 38, 39 Pass.
  - 35: two taps 0 ms apart sent one request and saved one submission; spinner shown, `aria-disabled=true` while busy.
  - 39: “Cannot reach the backend at http://127.0.0.1:8001…”; the app stayed on the Check screen and kept the text.

The web cases ran in headless Edge, not on a phone, so check 35–39 on the iPhone as well if the sheet needs
device evidence.
