# KhabarNazar development readiness audit

**Date:** 2026-11-21. **Commit audited:** `8411e29` on `main`, in sync with `origin/main`. **Machine:** home PC,
Windows 11, 15.7 GB RAM, CPU only.

**Verdict: READY WITH LIMITATIONS** for major testing, once the web fix in `app/+html.tsx` (made during this
audit, not yet committed) is committed. Every critical workflow was run end to end with real model inference,
real OCR, real Grad-CAM and the real UI. The limitations below should be known before writing test cases.

Status words: **Verified** (run during this audit, evidence given), **Partial** (works, with a gap),
**Broken**, **Missing**, **Not verified** (not run in this audit).

## How it was checked

| Step | What ran | Result |
|---|---|---|
| A | `pytest` (mocked models, temporary SQLite) | 151 passed, 13 skipped |
| B | `pytest --postgres` (isolated `khabarnazar_test` database) | 151 passed, 13 skipped |
| C | `pytest --real-models -m real_models` (real XLM-R, TF-IDF, EasyOCR, detector, Grad-CAM) | 13 passed |
| D | `alembic check`, `alembic current`, `scripts/describe_database.py --check` | no pending changes; head `e5b1c7a3d920`; docs match |
| E | `pytest text_module/tests` | 3 passed |
| F | `npx tsc --noEmit`, `npx expo-doctor` | clean; 20/20 checks |
| G | End-to-end HTTP smoke test: a separate uvicorn on port 8001, real models, throwaway SQLite database and upload folder (the real database was not touched) | 52 checks passed. The first run reported 4 failures; they were a bug in the test script (it read `gradcam_status` from the wrong level), re-checked by hand, and all 4 Grad-CAMs had completed |
| H | UI walk-through of the web build in a browser against the same test backend | see section 2 |
| I | Direct detector run on 6 images, comparing the ensemble label with the ResNet18 member that Grad-CAM explains | 1 of 6 disagree |

The test scripts (`e2e_smoke.py` and its results JSON) were kept outside the repository, in the session scratch
folder.

## 1. Overall readiness

The critical paths work with real models:
- registration and login, then a text check (Urdu, Roman Urdu, long Urdu, English) to its result and history;
- image upload, then OCR, text classification, image analysis and Grad-CAM, then the image result screen and
  history;
- a dispute, then admin review and override, then the updated verdict.

One blocking bug was found and fixed during the audit: the web build of the app did not load at all
(section 14). The other findings are medium or low; see sections 14 and 15.

## 2. Frontend: Partial (native verified earlier, web verified in this audit after the fix)

| Item | Status | Evidence |
|---|---|---|
| App starts (web) | Verified after fix | Before the fix the HTML had no `<script>` tag (`curl /login`, and `expo export --platform web` gave pages with no bundle reference). After the fix the bundle loads and the sign-in screen renders (step H) |
| App starts (iPhone, Expo Go SDK 58) | Not verified in this audit | The Metro and backend logs of 18 Nov showed the iPhone bundling SDK 58 and loading login, history, images and heatmaps with HTTP 200 |
| Registration, login, sign-out | Verified (H) | Registered `web.audit@example.com`, landed on Check; signing out removed the token and returned to `/login` |
| API base URL | Verified | `EXPO_PUBLIC_API_URL` from `.env`, overridable through the environment; `/api/v1` appended in `lib/api.ts` |
| Token storage | Verified (code) | `lib/tokenStorage.ts`: SecureStore on native, AsyncStorage (localStorage) on web; the profile is kept apart from the token |
| Expired session during use | Verified (code) | `setUnauthorizedHandler` in `AuthContext`: a 401 clears the session, shows "Session expired" and redirects to `/login` |
| Expired session at app start | Partial | A corrupted token, then reloading `/history`: the token was cleared but the user **stayed on History** ("0 checks saved"). Only `app/index.tsx` and `app/admin/_layout.tsx` redirect; `(tabs)`, `result` and `dispute` have no guard. No data leaks (every API call returns 401) |
| Text submission and result | Verified (H) | Roman Urdu headline: spinner while busy, then `/result/10`: "Likely credible", score 99.7%, risk 0.3%, detected Roman Urdu, 8 influential words, all matching the API record |
| Image upload and result | Verified (H) | Rendered news image, through Gallery, Analyze, `/result/11`: authenticity "Likely AI-generated 86.0%", Grad-CAM overlaid on the centre crop, OCR text, Roman Urdu verdict "Likely misleading 84.7%", influential words |
| History | Verified (H) | Shows only the signed-in user's checks, with the "Dispute pending" badge |
| Disputes | Verified (H) | Form sent, then the result shows the reason, the evidence link (normalised to `https://`) and "Waiting for an administrator" |
| Admin | Verified (H) | Admin card and tab badge, dispute queue, review screen; the override to "Misleading" was saved (the API shows `final_label=Fake`, `source=Admin`) |
| Loading, empty and error states | Verified (code and H) | Analyze shows a spinner and is disabled while busy; empty history and an empty queue have messages; a network failure says "Cannot reach the backend at …" |
| Mock or placeholder data | None found | `grep` for mock, dummy, lorem, TODO and demo found only a comment in `types/submission.ts:63` |
| Password reset | Missing (stated) | `app/(auth)/forgot.tsx` tells users that reset is not available |

## 3. Backend: Verified

FastAPI starts; `/health` reports the database as connected and `migrations: up_to_date`. In G:
- **Authentication:** register and login work. A wrong password and an unknown email return the same 401
  message, a bad token gets 401, and `/users/admin-test` returns 404 (removed).
- **Validation:** empty, whitespace-only and over-length text, a missing field, corrupt files, non-images,
  GIFs and uploads over 10 MB are all rejected (422/415/413).
- **History and ownership:** history is isolated per user. Another user gets 404 for my submission, its image
  and its heatmap, and cannot dispute it.
- **Admin:** a non-admin gets 403 on `/admin/*`, and the admin stats and list work.

## 4. Database: Verified

PostgreSQL 17 (`khabarnazar`, role `khabarnazar_app`) is migrated to head `e5b1c7a3d920` (adds
`image_submissions.ocr_status`). `alembic check` finds no differences between the models and the migrations,
and the schema docs match (step D). SQLite works too (G used it). Submissions are saved and read back:
`GET /submissions/{id}` after each POST returns the stored values.

## 5. Urdu model: Verified

- **Routing:** Urdu script (and mixed text that is mostly Urdu) goes to the Urdu XLM-R; Urdu over 150 words goes
  to the long-article TF-IDF.
- **Labels:** label maps are read and checked from `config.json` (`text-model-v1`: REAL/FAKE).
- **Length:** 64 tokens for this PC's `text-model-v1`, and 256 for the `urdu-xlmr-v1` release.
- **Inference (G):** a short Urdu headline gave Real 0.9996 with `text-xlmr-hookbait` in 0.9 s; about 200 words
  of Urdu gave Real 0.599 with `tfidf-urdu-long-articles`.

**Note:** this PC loads the older `text-model-v1` (`models/text/xlmr/`). A fresh clone (and the university PC)
loads `urdu-xlmr-v1`, so the two PCs can give different Urdu results. Pick one before formal testing.

## 6. Roman Urdu model: Verified

`xlmr-roman-urdu` (XLM-R large, labels Real/Fake, 512-token limit; no `KHABARNAZAR_XLMR_MAX_LEN` override in
`.env`). In G a Roman Urdu headline gave Fake 0.9976.

**Latency:** the Roman Urdu model took **14.3 s** for that request on this CPU.

**English:** there is no English model. English goes to the Roman Urdu model and the summary says it is less
reliable; in G English gave Real 0.9934 with `xlmr-roman-urdu`. Text with no letters returns Uncertain with no
score.

## 7. EasyOCR: Verified

Urdu and English readers load from `backend/.cache/easyocr` (285 MB).
- **Urdu image:** OCR read the Urdu headline fixture at confidence 0.44, detected Urdu and classified it.
- **Roman Urdu image:** OCR read it at 0.64, detected Roman Urdu and classified it.
- **Photo without text:** `ocr_status=no_text_found` and no claim verdict.

OCR failure (mocked) is reported and does not stop the image analysis (unit tests in A).

## 8. Image analysis: Verified, with a product limitation

- **Coverage:** every valid image goes through the CLIP + DINOv2 + robust-ResNet18 ensemble, including images
  with text (G: `image_score` present for all 4 images).
- **Original kept:** the original upload is kept byte for byte (G: downloaded file equals uploaded bytes).
- **Rotation:** EXIF rotation is handled. A JPEG stored 900×600 with Orientation 6 got a 600×900 heatmap,
  matching the upright original.

**Limitation (observed):** all three computer-rendered text images were rated AI-generated at 86–98%. These
were the Urdu headline fixture (94%), a Roman Urdu text image (98%) and the web-UI test image (86%). The detector
was trained on photos (AI vs Real, Tiny-GenImage, Misinfo), so news screenshots are likely to be reported as
"Likely AI-generated". Since the result screen now shows image authenticity first, in red, this is the most
visible risk for testers and users.

## 9. Grad-CAM: Verified, with a mismatch

A heatmap was produced and stored for all 4 images in G (`gradcam_status=completed`). It is placed over the
analysed centre crop of the upright original, and on the web result it is drawn over the original image.

**Mismatch (I):** Grad-CAM explains the **ResNet18 member's** predicted class, but the label shown is the
**three-model average**. In 1 of 6 images they disagree: the rotated photo has ensemble P(real) 0.572 ("Likely
real photo"), but ResNet18 P(real) 0.278, so the heatmap explains "AI-generated".

## 10. Evaluation pipeline: Verified

`app/ai/pipeline.py` `evaluate()` takes the verdict and the risk **only** from the text classification. Image
authenticity and Grad-CAM are reported separately and never averaged with it. An image with no usable text gets
"Uncertain" and no risk score (G: the no-text photo got `final_label=Uncertain` and `combined_risk_score=None`
with `image_score=0.78`).

## 11. Frontend/backend integration: Verified

All six workflows in the brief were run through the real UI or over HTTP (G and H). The response fields the app
reads (`image_submission.image_analysis_status`, `analysis_branch`, `ocr_status`, top-level `gradcam_status`,
`explainability.*`) are present and match `lib/api.ts` and `lib/SubmissionsContext.tsx`.

## 12. Automated smoke-test results

See "How it was checked". Every suite passed. Real-model tests ran with the actual trained files (C, G, I).
**Not run:** a clean install on a fresh machine, the iPhone app in this audit, and the Android app.

## 13. Missing dependencies and files

- **Nothing required is missing on this PC.** All model folders, the EasyOCR weights and the Hugging Face
  backbones are present.
- **Not in GitHub, by design:** see `docs/UNIVERSITY_PC_SETUP.md`. The XLM-R weights download from Releases, and
  the backbones and OCR weights download on first use.
- **Missing everywhere:** the training and evaluation datasets, so the reported model metrics cannot be
  re-measured.

## 14. Critical bugs

1. **The web build would not load. Fixed during the audit; not committed yet.** Expo Router 58 passes the page's
   `<script>` and `<style>` tags through `useServerDocumentContext()`, and the old custom `app/+html.tsx` did not
   render them. The result was a blank page on web in development and in `expo export` builds. The fix renders
   `headNodes`, `bodyNodes` and the html/body attributes. Afterwards the type-check was clean, the export has
   script tags, and the UI walk-through passed. Native apps were not affected, since `+html.tsx` is web-only.
   This was caused by the SDK 58 upgrade in `8644f06`.

No other critical bugs found.

## 15. Non-critical issues

| # | Issue | Severity |
|---|---|---|
| 1 | Screenshots and rendered text images are rated "Likely AI-generated" with high confidence (section 8) | High (product) |
| 2 | Grad-CAM explains the ResNet18 member, not the label shown; they disagreed in 1 of 6 images | Medium |
| 3 | No route guard on `(tabs)`, `result` and `dispute`: after a session expires at start-up, or via a deep link, the user stays on an empty protected screen | Medium |
| 4 | "Likely AI-generated" uses the same red as a "Fake" news verdict | Low |
| 5 | The two PCs use different Urdu checkpoints (section 5) | Medium (for testing) |
| 6 | Latency on CPU: Roman Urdu 9–15 s per request, images 7–16 s; about 5 GB RAM with every model loaded | Medium (for testing) |
| 7 | English goes to the Roman Urdu model (documented and stated in the result) | Limitation |
| 8 | Password reset not implemented (stated on screen) | Limitation |
| 9 | `react-test-renderer` 19.1 sits beside React 19.3 (unused); `npm audit` reports 3 moderate | Low |
| 10 | Commit `ea1a622` (14 Nov) contains a `Co-Authored-By: Claude` trailer | Housekeeping |
| 11 | A stale stash from before the 17 Nov sync is still kept (`git stash list`) | Housekeeping |

## 16. Recommended fixes, in priority order

1. Commit and push the `app/+html.tsx` fix, then re-test the web build on the university PC.
2. Decide how image authenticity is presented for screenshots, for example lead with the text verdict when OCR
   found usable text, and keep authenticity as a secondary card. Then measure the detector on a small set of real
   news screenshots before formal testing.
3. Make Grad-CAM explain the ensemble's label: back-propagate the ResNet18 logit of the class the ensemble chose,
   and keep the caption saying it is the ResNet18 view.
4. Add a signed-in guard to the `(tabs)`, `result` and `dispute` layouts (redirect to `/login` when there is no
   user once `ready`).
5. Choose one Urdu checkpoint for testing and use it on both PCs.
6. Plan test timeouts for CPU latency, or run formal tests on a machine with more RAM or a GPU.
7. Use a neutral colour for "Likely AI-generated".

## 17. Final recommendation

**READY WITH LIMITATIONS**, on two conditions: fix 1 is committed, and testers know about items 1, 2, 5 and 6 in
section 15.
- **Verified:** real inference works for Urdu, long Urdu, Roman Urdu and English. OCR, image analysis and Grad-CAM
  all run for every image. The evaluation keeps the outputs separate. The frontend shows the real results.
- **Not cleared for formal testing:** image-authenticity results on screenshots, until item 2 is decided.

---

## Finalization — 2026-11-21 (after the audit)

Work done to close the audit's open items. Every result below was run on this PC on 2026-11-21; nothing is
carried over from earlier runs.

### Changes implemented

| Audit item | Change | Files |
|---|---|---|
| Web build (critical) | Already committed in `3c351e9`. Re-verified: every exported page carries its scripts, `lang`, style reset, favicon and background CSS; the static build, served from disk, loads and redirects to `/login` | `app/+html.tsx` (no new change) |
| Urdu checkpoint | **Every PC uses release `urdu-xlmr-v1`** (see below). The backend now prefers `text_module/urdu/models/xlmr/` whenever it is complete, and the older `models/text/xlmr/` only when the release is missing. An explicit `KHABARNAZAR_URDU_XLMR_DIR` still wins. No checkpoint was deleted | `backend/app/ai/text/xlmr.py`, `backend/tests/conftest.py`, setup guide, README, `.env.example` |
| Image authenticity on screenshots | Investigated on 30 images (below). Presentation changed: when text read from the image was classified, its **verdict comes first**; image authenticity follows as a separate, clearly labelled card in a **neutral colour** (not the red/green of news verdicts), with every number still shown, plus a statement of the detector's known weakness. The backend summary carries the same caveat. Nothing is hidden or altered | `app/result/[id].tsx`, `backend/app/ai/image/predict.py` |
| Grad-CAM consistency | Grad-CAM now back-propagates ResNet18's logit for the **class the ensemble shows**, so the heatmap explains the label on screen. The ensemble probability is unchanged (Grad-CAM only reads gradients after the forward pass). Captions say it is a ResNet18-based explanation that does not cover CLIP or DINOv2. When ResNet18 is near-certain of the other class, the map is flat and no heatmap is invented; the reason is reported | `backend/app/ai/image/ai_detector.py`, `predict.py`, `submission_service.py`, `app/result/[id].tsx` |
| Route guards | One signed-in guard in the root layout (`useSignedInGuard`). It runs only after the session check (`ready`), and sends signed-out users from every non-public route (`(tabs)`, `result`, `dispute`, `admin`, `profile`, anything added later) to `/login`. The admin role check in `app/admin/_layout.tsx` is unchanged | `app/_layout.tsx` |

**Selected Urdu checkpoint: release `urdu-xlmr-v1`** (`text_module/urdu/models/xlmr/`).
- **Model:** `XLMRobertaForSequenceClassification` (xlm-roberta-base, 12 layers, hidden size 768).
- **Labels:** `config.json` `id2label` {0: real, 1: fake}, read and checked at load.
- **Tokenizer:** `XLMRobertaTokenizer` from `tokenizer.json`, loaded with `local_files_only`.
- **Maximum length:** 256 tokens (the training notebook's `MAX_LEN` for run E1).
- **Preprocessing:** the notebook's `clean_urdu`, with punctuation kept.
- **Model version string:** `xlmr-urdu`.

Why this one:
- It is the only Urdu checkpoint that can still be downloaded (the `text-model-v1` release returns 404).
- `text_module/download_models.py urdu` fetches it.
- The university PC already uses it.

**University PC:** run `python text_module/download_models.py urdu` and do not set `KHABARNAZAR_URDU_XLMR_DIR`. The check
command in `docs/UNIVERSITY_PC_SETUP.md`, step 6, must print `text_module\urdu\models\xlmr True 256` for Urdu.
**Verified here:** `xlmr.model_dir('urdu')` now resolves to `text_module\urdu\models\xlmr` and loads with
max_len 256, labels {0: real, 1: fake}, fake index 1, notebook cleaning.

### Image authenticity: what was found (no accuracy claimed)

The real detector was run on 25 local uploads (your own phone tests) and 5 rendered variants. The images were
grouped by eye; their true labels are not known.

| Group | Rated AI-generated | Ensemble P(AI) range |
|---|---|---|
| Text graphics / screenshots (5) | 5 of 5 | 0.69 – 0.98 |
| Rendered text: light, dark, colour, JPEG q60, photo with a caption bar (5) | 5 of 5 | 0.63 – 0.99 |
| Camera photos that look real (12) | 7 of 12 | 0.62 – 0.77 for those 7 |
| Images that look AI-made (8, including 2 memes) | 8 of 8 | 0.79 – 0.98 |

Why the detector behaves this way:
- **Training data:** it was trained on camera photos versus generated images (AI vs Real, Tiny-GenImage),
  with Misinfo held out for testing. None of these contain screenshots or text graphics.
- **What it sees:** after preprocessing (shorter side 512, 224×224 centre crop) a screenshot reaches the model
  as a crop of flat background and text.
- **Earlier evidence:** notebook 05 already reports that only 84% of real Misinfo photos were accepted.

So for screenshots, posters and many re-shared web photos, the detector's output is **not reliable**. This is a
limitation of the training data, not something that can be fixed without new data. **Validating it properly
needs a labelled set of real news screenshots and web photos, which the project does not have.**

### Grad-CAM consistency: verified

- **Real models, 26 images:** ResNet18 on its own disagreed with the label shown on 4 images. With the change,
  the heatmap explains the shown class on all 26 (0 mismatches, down from 4).
- **Flat maps:** on 2 of those 4 images ResNet18 is near-certain of the other class, so the map for the shown
  class is flat. No heatmap is shown, and the reason ("ResNet18 leaned strongly the other way …") is reported.
- **New regression tests in `tests/test_image_gradcam.py`:**
  - disagreement case (ensemble "real", ResNet18 "AI");
  - the target class follows the ensemble;
  - `analyze_image` reports the explained class;
  - the no-evidence case.

### Tests executed (2026-11-21, on the final code)

| Check | Result | Audit |
|---|---|---|
| `pytest` (mocked, SQLite) | 156 passed, 13 skipped | 151 / 13 |
| `pytest --postgres` | 156 passed, 13 skipped | 151 / 13 |
| `pytest --real-models -m real_models` (now with `urdu-xlmr-v1`) | 13 passed | 13 |
| `alembic check` / `current` / `describe_database.py --check` | no changes / `e5b1c7a3d920` / docs match | same |
| `pytest text_module/tests` | 3 passed | 3 |
| `npx tsc --noEmit` | clean | clean |
| `npx expo-doctor` | 20/20 | 20/20 |
| `expo export --platform web` | built; pages carry 5–7 script tags | was broken |
| `expo export --platform ios` | bundle built (3.9 MB) | built |
| End-to-end HTTP smoke test (real models, throwaway database) | 52 passed, 0 failed | 52 (after the script fix) |
| Route guards in the browser (web dev build against the test backend) | all four scenarios pass (below) | was failing |

The five new tests are the 4 Grad-CAM tests and 1 checkpoint-selection test.

**Route-guard scenarios** (real browser, page reloads and deep links):
- **Signed out:** `/history`, `/result/10`, `/dispute/10`, `/admin` and `/profile` all ended on `/login`, and
  `/register` stayed open.
- **Valid session:** reloading `/history` (2 checks shown) and `/result/11` kept the user there, and a
  non-admin opening `/admin` was sent to `/`.
- **Expired token at start:** the token and profile were cleared and the app landed on `/login`. Before this
  change it stayed on an empty History screen.
- **Admin:** `/admin` and `/admin/disputes` opened the moderation desk.

### Remaining limitations and unresolved issues

1. **Image authenticity is not reliable on screenshots and many web photos** (above). The presentation is now
   honest about it, but the model itself is unchanged. Testers should record authenticity results on
   screenshots as known behaviour, not as new bugs. They should not be counted as defects unless the
   presentation is wrong.
2. **Some heatmaps are missing:** when ResNet18 disagrees strongly with the ensemble (2 of 26 images here),
   no heatmap is shown.
3. **CPU latency** (Roman Urdu up to about 14 s per request, images 6–14 s) and **about 5 GB of RAM** with every
   model loaded.
4. **English** is classified by the Roman Urdu model (stated in the result). **Password reset** is not
   implemented.
5. **Not run in this pass:** the iPhone app, Android and a clean install on a fresh machine.
6. **Housekeeping:** the `Co-Authored-By: Claude` trailer in `ea1a622`, a stale git stash, and
   `react-test-renderer` 19.1 next to React 19.3 (unused).

### Final recommendation

**READY FOR MAJOR TESTING**, with limitations 1–5 written into the test plan. Every audit item was addressed
and verified:
- the web build works;
- one Urdu checkpoint is used everywhere;
- the image-result hierarchy separates the news verdict, image authenticity and Grad-CAM;
- Grad-CAM explains the label shown;
- the route guards work.

Image-authenticity results on screenshots are presented acceptably for testing, but they are **not** evidence of
model accuracy.
