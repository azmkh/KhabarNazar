# Image module test results: TC-IMG-01 to TC-IMG-45 (2026-11-28)

The image test cases from `KhabarNazar — Image Module Test Cases.xlsx` were run against the real backend with
the real models (EasyOCR, the CLIP + DINOv2 + ResNet18 ensemble, Grad-CAM and the text models).

| Output | File |
|---|---|
| Raw responses | `backend/tests/image_cases/results_2026-11-28.json` |
| Sheet columns E/F | `backend/tests/image_cases/results_2026-11-28.csv` |
| Detector measurements | `backend/tests/image_cases/probe_2026-11-28.json` |
| Inputs | `backend/tests/image_cases/images/` (with `manifest.json`) |
| Heatmaps | `backend/tests/image_cases/heatmaps/` |
| Screenshots | `backend/tests/image_cases/screens/` |

This was a testing-only pass. No application code, model, checkpoint, label map, preprocessing step, OCR cutoff
or threshold was changed, and no model or cache file was renamed or deleted.

## 1. Environment

| Item | Value |
|---|---|
| Machine | HP Laptop 14-dq2xxx, Intel Core i5-1135G7 @ 2.40 GHz, 16 GB RAM, Windows 11 Home, CPU only; Python 3.14.4, torch 2.14.1+cpu, transformers 5.20.2, Pillow 12.3.0, `PYTHONUTF8=1` |
| Branch / commit | Checked out: `main` at `0087378`. Working tree is clean apart from untracked test output. The `deploy` tip is `a623335`, and `git diff deploy HEAD -- backend text_module image_module` (tests excluded) is **empty**, so the backend and models tested are exactly the `deploy` tip. The web build differs from `deploy` only in the role-based redirect, the admin header and the Check-screen info card, none of which is on the image check path. |
| Backend under test | Separate uvicorn on port 8001 (`tests/full_pass/start_test_server.py`), throwaway SQLite database built by the Alembic migrations, its own uploads folder (both in the session scratch folder), all models preloaded. The real PostgreSQL database and the real `backend/uploads` folder were not used. The developer backend on port 8000 was stopped during the run to free RAM, then restarted. |
| Accounts | Test users A and B, plus an admin made with `scripts/set_user_role.py` on the throwaway database |
| Text models | Urdu `urdu-xlmr-v1` (`xlmr-urdu`, 256 tokens), Roman Urdu `xlmr-roman-urdu` (512 tokens). Same files and SHA-256s as in `TEXT_TEST_RESULTS_2026-11-28.md` |
| Image ensemble | `img-ens-clip-dino-r18` from `image_module/models`. `resnet18_robust.pth` `93bf9770…c2`, `clip_vitl14_head.joblib` `75062f7b…09`, `dinov2_l_head.joblib` `8a9d91dc…2f`. Backbones `openai/clip-vit-large-patch14` and `facebook/dinov2-large` come from the local Hugging Face cache. |
| OCR | EasyOCR, languages `ur` + `en`, CPU. Weights in `backend/.cache/easyocr`: `craft_mlt_25k.pth` `4a5efbfb…17`, `arabic.pth` `2a9afd42…a8` |

### Preflight values found in the code

| Setting | Value and where |
|---|---|
| Allowed types | JPEG, PNG and WEBP, detected from the bytes with Pillow, not from the name or Content-Type (`app/utils/upload.py`). Anything else gets 415: “Unsupported image format 'gif'. Accepted: JPEG, PNG, WEBP.” or “File does not appear to be a valid image.” |
| Size limit | `MAX_UPLOAD_SIZE_MB = 10`, i.e. 10,485,760 bytes; larger files get 413. There is also a pixel cap, `MAX_IMAGE_PIXELS = 40,000,000`: larger images get 413 “Image dimensions are too large to analyze.” (`app/config.py`, `upload.py`). |
| OCR cutoff | `OCR_MIN_CONFIDENCE = 0.3` **and** `OCR_MIN_LETTERS = 10`. The confidence is the mean over EasyOCR detections, and text below either value is not classified (`has_usable_text`, `app/ai/image/ocr.py`). |
| `ocr_status` values | `completed`, `no_text_found`, `unavailable` (OCR raised or could not start) and `dependency_missing`. There is no `failed` value. |
| Preprocessing | RGB, shorter side scaled to 512 (never below 224, bicubic), then a 224×224 centre crop and per-backbone normalisation (`standardise` / `crop_box`, `app/ai/image/ai_detector.py`). EXIF orientation is applied first (`upright_image`, `preprocess.py`). The ensemble is the mean of P(real) from three members, thresholded at 0.5. |
| Grad-CAM class | `AIImageDetector._resnet_with_gradcam` (`ai_detector.py`) takes the ensemble's class (the other two members' P(real) plus ResNet18's, divided by 3, against 0.5) and back-propagates ResNet18's logit for that class at `layer4[-1]`. A flat map means no heatmap. When ResNet18 disagrees, the reason given is that it “leaned strongly the other way”. |
| Rate limit | Shared with text checks: `CHECK_RATE_LIMIT_PER_MINUTE = 10`, `CHECK_RATE_LIMIT_PER_HOUR = 100` per user, set by env vars of the same names (`app/utils/rate_limit.py`, dependency `limit_checks`). The main run raised them through those env vars; TC-IMG-39 ran on a fresh server with the real values. |
| App timeout | `ANALYSIS_TIMEOUT_MS = 180_000` in `lib/api.ts`. The runner used 180 s, or 900 s for the parallel TC-IMG-39 uploads. |

### Test images

Every asset was made for this pass. Nothing was downloaded, and no real upload was copied. `images/manifest.json`
records how each file was made, its size and its SHA-256.

- **Urdu rendering.** The Pillow here has no raqm and `arabic_reshaper` is not installed, so Pillow cannot join
  Urdu letters. Text images were therefore rendered by headless Edge, which shapes Urdu correctly. Urdu uses
  **Noto Nastaliq Urdu** from the app's own `node_modules/@expo-google-fonts` (embedded as a data URL). Latin
  text uses Segoe UI. All text is black on white at 1200×600.
- **Photos.** The repo's only image fixture is `backend/tests/fixtures/urdu_headline.png`, which was used for
  TC-IMG-06. All photo-like images are **synthetic** (numpy and Pillow: landscape, street, texture, portrait and a
  smooth “AI-look” image) and are labelled as such.
- **Controls.** The TC-IMG-02 and TC-IMG-10 texts were also rendered in Segoe UI, a Naskh-style Arabic-script
  face. They are not test-case inputs; they show whether a low OCR score comes from the Nastaliq font.

The fault-injected cases are TC-IMG-01, 28, 29 and 30 only. They ran in a child test process (FastAPI TestClient
on the same throwaway database and uploads folder):

| Case | What was patched |
|---|---|
| 01 | OCR loader raises, and `load_detector` returns no detector |
| 28 | EasyOCR `readtext` raises |
| 29 | The real detector loads, then its `analyse` raises |
| 30 | `torch.Tensor.backward` raises, which only the Grad-CAM backward pass uses |

The API does not return the members' probabilities or the class Grad-CAM explained. So a read-only probe ran the
same detector code on each asset (`probe_2026-11-28.json`); the evidence quotes “explained class” from it.

## 2. Totals

| Result | Count | Cases |
|---|---|---|
| Pass | 33 | 01, 03, 04, 05, 07, 09, 12, 13, 14, 16–19, 21–32, 34–36, 38–40, 42, 44 |
| Fail | 3 | 02, 10, 15 |
| Finding | 6 | 08, 11, 20, 37, 43, 45 |
| Known limitation | 1 | 06 |
| Not run | 2 | 33 (no qualifying image found), 41 (iPhone HEIC; needs the phone) |

## 3. Failures

| Case | Input | Expected | Actual | Suggested severity | Likely file |
|---|---|---|---|---|---|
| TC-IMG-02 | Rendered Urdu headline in Noto Nastaliq Urdu, black on white, 1200×600 | OCR reads it; Urdu; verdict from `xlmr-urdu`; `image_score`; heatmap | OCR confidence **0.28**, below the 0.3 cutoff. The text was read with errors (“کیاے کەملک بجھریں”), so `ai_or_real`, no text verdict and final Uncertain. `image_score` 0.83 and the heatmap were present. **Control:** the same text in Segoe UI reads at 0.52 and gives `xlmr-urdu` Real. | **High**: Nastaliq is the usual typeface for Urdu news, so screenshots of Urdu headlines often get no verdict | `app/ai/image/ocr.py` (EasyOCR `ur` uses the Naskh-trained `arabic.pth`), `OCR_MIN_CONFIDENCE` in `app/config.py` |
| TC-IMG-10 | Rendered 4-line Urdu paragraph (Nastaliq) | OCR text in reading order; text verdict | OCR 0.27 → no verdict. The 9 OCR fragments map to source lines **1, 2, 3, 1, 2, 4, 4, 3, 3**, which is not reading order. The Segoe UI control reads at 0.63 and gets a verdict, but its lines are also out of order (1, 2, 1, 3, 3, 4, 1, 1, 2, 1). | **Medium**: multi-line Urdu reaches the text model scrambled even when it is classified | `app/ai/image/ocr.py` `run_ocr`: `readtext(…, paragraph=False)` joins detections in detection order, not right-to-left, top-to-bottom |
| TC-IMG-15 | Synthetic street photo with Roman Urdu meme text (white Impact-style capitals with a black outline) | Both paths: OCR text verdict and `image_score`; heatmap | OCR read garbage (“IBIB آST٥٥ / IUPIBUfIEISUPBISSSTIOJI”) at 0.06, so no verdict. The image analysis (AI 0.45, Likely real photo) and the heatmap ran. | Medium: meme-style captions are not read | `app/ai/image/ocr.py` (EasyOCR on outlined capitals) |

None of these is a crash or a wrong route. In each case the cutoff rule worked as designed: low-confidence text
is not classified, and the picture is still analysed. They fail because the image-with-text path did not produce
the expected verdict for these common inputs.

## 4. Findings

| # | Case | Finding |
|---|---|---|
| F1 | TC-IMG-08 | The English image goes to `xlmr-roman-urdu` as expected, but OCR inserted an Arabic-script letter (“for\nalا\npublic”). The text was detected as **mixed**, so the summary shows the mixed-script note instead of the English lower-reliability note. |
| F2 | TC-IMG-11 | The blurred image read at 0.00, so the text check was skipped with the reason “OCR found only a little or unclear text…”; image analysis and the heatmap ran. The light-grey image still read at **0.41**, above the cutoff, so its text was classified (`xlmr-urdu`). Only the blurred variant exercised the below-cutoff path. |
| F3 | TC-IMG-20 | A 1×1 PNG returns 201 with no verdict (final Uncertain), but the detector upscales it to 224×224 and still reports an AI-generated score (0.50), a label and a heatmap. A minimum-size check or a “too small to analyse” message would be clearer. |
| F4 | TC-IMG-37 | History is newest first, and none of the 6 rejected files appears (every listed image's SHA-256 was compared). But the list response (`SubmissionListItem`) has **no OCR text and no `image_score`** for image checks: `text_preview` is filled for text checks only. They are only in the full record. |
| F5 | TC-IMG-43 | The no-text result says “No readable news text was found in this image, so no news claim was checked.” and shows the authenticity card and heatmap. However, no verdict card is shown and the word **Uncertain** (the stored final label) does not appear on screen. |
| F6 | TC-IMG-45 | Each bad file is refused with a clear message, but none of them uses the use case's “Invalid file type. Please upload a valid image”. |

TC-IMG-45 messages:

| File | Message | Request sent? |
|---|---|---|
| `.txt` | “Unsupported file type: text/plain. Only images and videos are supported.” (from the image picker) | No |
| Text renamed `.png` | “Could not analyze — File does not appear to be a valid image.” (from the backend, 415) | Yes |
| PNG over 10 MB | “This image is larger than 10 MB. Choose a smaller one or a screenshot.” (from the app) | No |

Other observations, with no result changed:

- TC-IMG-06 matches the earlier report exactly: OCR 0.44, Real 0.9999, AI 0.9434 (Known limitation).
- TC-IMG-09: mixed Urdu + “petrol” read at 0.43 and was classified, but the OCR text has junk around the words
  (“ي ی کا اعلان نياء حکومت نے petrol ئ قیمت”).
- TC-IMG-21: 8000×8000 is refused at once (413, pixel cap). The extra 6000×6000 image took 51.9 s, and the server's
  peak working set over the run was 7.5 GB.
- TC-IMG-26: the EXIF-6 image was analysed upright. OCR read the upright text and the heatmap is 600×900.
- TC-IMG-32: in `f16_valid.jpg`, ResNet18 disagrees (P(real) 0.92 against the ensemble's 0.45). The heatmap was
  produced for the ensemble's class (“fake”), not ResNet18's own.
- TC-IMG-33 Not run: no asset made ResNet18 near-certain of the other class. Both disagreeing assets (`f16`,
  `img15`) still got a heatmap, so the missing-heatmap path did not occur.
- TC-IMG-28 Pass: the failed-OCR value is `unavailable`, not `failed` (the code has no `failed` value). It is
  distinct from `no_text_found`, and the result screen shows “Text reading (OCR) failed on this image”.
- **Substitute image for TC-IMG-29 and TC-IMG-35.** Both need TC-IMG-02 to produce a text verdict, which it did not
  (TC-IMG-02 Fail). They used the repo fixture `urdu_headline.png` (TC-IMG-06) instead, and say so in their
  evidence.
  - 29: detector failure → image analysis unavailable, no score or heatmap, OCR verdict (Real) kept.
  - 35: final risk 0.0001 equals the text risk; the average with `image_score` 0.9434 would have been 0.47; no text → risk None.

## 5. AI-generated score by image type

`image_score` is the ensemble's probability that the picture is AI-generated (1 − P(real)). These are not pass/fail
judgements; the images are synthetic and have no ground truth.

| Image type | Checks | AI score | Label |
|---|---|---|---|
| Urdu text, Nastaliq (02, 09, 10, 11-grey, 26) | 9 | 0.73–0.88 | all Likely AI-generated |
| Urdu text, Nastaliq, blurred (11) | 1 | 0.62 | Likely AI-generated |
| Urdu text, Segoe UI (fixture, controls) | 3 | 0.92–0.94 | Likely AI-generated |
| Roman Urdu text, Segoe UI (07, 18, 25) | 3 | 0.95 | Likely AI-generated |
| English text, Segoe UI (08) | 1 | 0.96 | Likely AI-generated |
| Screenshot-style news card (13) | 1 | 0.39 | Likely real photo |
| Synthetic photo + Urdu caption strip (12) | 1 | 0.39 | Likely real photo |
| Meme on synthetic photo (15) | 1 | 0.45 | Likely real photo |
| Synthetic photo-like, no text (03, 16, 17, 19) | 6 | 0.29–0.85 | 3 real, 3 AI |
| Synthetic smooth “AI-look” (14) | 1 | 0.76 | Likely AI-generated |
| Tiny (1×1) (20) | 1 | 0.50 | Likely AI-generated |
| Large / noise (21b, 22a) | 2 | 0.27–0.63 | 1 real, 1 AI |

Every plain rendered-text image (white background) was rated AI-generated, as the audit's Finalization section
describes. Images with a photo area (news card, caption strip, meme) were rated real.

## 6. OCR confidence by image type

| Image type | OCR confidence | Classified? |
|---|---|---|
| Urdu, Nastaliq, single headline (02, 26) | 0.28, 0.38 | 02 no, 26 yes |
| Urdu, Nastaliq, 4-line paragraph (10) | 0.27 | no |
| Urdu, Nastaliq, mixed with “petrol” (09) | 0.43 | yes |
| Urdu, Nastaliq, light grey (11b) | 0.41 | yes |
| Urdu, Nastaliq, blurred (11a) | 0.00 | no |
| Urdu, Segoe UI (fixture 06, control 02, control 10) | 0.44, 0.52, 0.63 | yes |
| Urdu caption strip on a photo (12) | 0.40 | yes |
| Screenshot-style card, header + Urdu headline (13) | 0.61 | yes (text detected as mixed) |
| Roman Urdu, Segoe UI (07) | 0.56 | yes |
| English, Segoe UI (08) | 0.66 | yes (detected as mixed) |
| Meme, outlined capitals (15) | 0.06 | no |
| Photos with no text (03, 14, 16, 17, 19, …) | — (`no_text_found`) | — |

Nastaliq text sits between 0.27 and 0.43, right around the 0.3 cutoff. The same Urdu text in a Naskh-style face reads
at 0.52–0.63.

## 7. Latency

Times are client-measured, from upload to response, on the throwaway server, which had every model loaded. The
fault-injected cases are excluded because their child process loads models on first use.

| Group | Checks | Median | Max |
|---|---|---|---|
| All accepted image checks | 31 | 12.6 s | 51.9 s (6000×6000) |
| With a text verdict (image pair) | 13 | 17.2 s | 33.5 s |
| Without a text verdict | 19 | 12.5 s | 51.9 s |
| Text verdict by `xlmr-roman-urdu` | 4 | 23.5 s | 33.5 s |
| Text verdict by `xlmr-urdu` | 9 | 17.2 s | 28.3 s |

Per case: 02 6.2/7.8 s · 03 10.7 · 06 10.4 · 07 32.4 · 08 10.7 · 09 14.6 · 10 8.0/18.9 · 11 17.1/17.8 · 12 17.2 · 13 24.1 ·
14 15.1 · 15 21.2 · 16 12.6 · 17 12.8 · 18 33.5 · 19 12.5 · 20 4.8 · 21 51.9 · 22 18.0 · 24 (next request) 5.7 · 25 14.6 ·
26 6.9 · 27 8.3 · 38 6.4/6.6 s.

Rejected uploads (04, 05, 22-over, 23, 24) were answered in under 0.1 s. In TC-IMG-39 the 429 came back in 0.05 s,
while 10 uploads were being processed in parallel.

The Roman Urdu image checks (07: 32 s, 18: 34 s) are above the audit's “6–16 s per image” figure for images, which
does not include the Roman Urdu text model (9–15 s on its own). They stay well inside the app's 180 s timeout.

## 8. Screen checks (headless Edge, phone size, Expo web against the test backend)

| Case | Result |
|---|---|
| TC-IMG-13 / 42 | Pass. The text verdict card (“Verdict on the text in the image”) comes first. The authenticity card follows with the label “Image authenticity (separate from the verdict above)” in the neutral info blue (rgb(56, 189, 248)), not the verdict red or green. It carries its limitation note (“…treat this as a hint, not proof”) and the screenshot/poster note. The heatmap card shows the Grad-CAM drawn over the original image with the analysed centre area outlined, and the OCR text is shown. |
| TC-IMG-34 | Pass. The screen caption reads “Grad-CAM from the detector's ResNet18 model (one of its three models)…”, and the API summary says it “does not cover the detector's other two models”. |
| TC-IMG-40 | Pass. The second image was picked after the first was removed with ×. One request was sent, one record saved, and the stored image's SHA-256 equals the second pick. |
| TC-IMG-43 | Finding F5. |
| TC-IMG-44 | Pass. Spinner and `aria-disabled=true` while waiting. With the backend killed mid-request: “Could not analyze — Cannot reach the backend at http://127.0.0.1:8001…”; no crash, still on the Check screen. |
| TC-IMG-45 | Finding F6. |
| TC-IMG-41 | Not run: a HEIC camera-roll photo can't be produced in a browser. |

What the code does with HEIC (TC-IMG-41): the picker (`app/(tabs)/index.tsx`) calls expo-image-picker with
`quality: 0.85` and does no conversion of its own. Before upload, the app refuses anything whose reported type is
not JPEG, PNG or WEBP (“Choose a JPG, PNG, or WEBP image.”). The backend accepts only those three, checked from the
bytes. So a HEIC photo works only if expo-image-picker hands back a JPEG. Your earlier iPhone run of checklist
step 16 recorded that case as Pass.

These screen checks ran in headless Edge, not on a phone. Repeat 13/42, 43 and 44 on the iPhone if the sheet needs
device evidence.
