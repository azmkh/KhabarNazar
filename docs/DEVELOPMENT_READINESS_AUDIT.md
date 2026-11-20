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
