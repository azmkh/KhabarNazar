# KhabarNazar — Backend Service

Welcome to the backend service for **KhabarNazar**, an AI-assisted misinformation decision-support platform for text and news images. The text API uses separate trained XLM-R checkpoints for Urdu script and Roman Urdu. English is accepted as input but classification is not connected.

The backend is built with **FastAPI**, **PostgreSQL**, **SQLAlchemy**, and **Alembic**, designed with a clean layered architecture that separates routers, services, database models, and AI inference engines.

---

## 1. Prerequisites

- Python 3.11+ (Python 3.11, 3.12, 3.13, or 3.14)
- PostgreSQL 14+ (or SQLite for initial lightweight local development)
- Git

---

## 2. Setting Up the Virtual Environment

### Windows (PowerShell)
```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### Linux / macOS (Bash)
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
```

---

## 3. Installing Dependencies

Make sure your virtual environment is active, then upgrade pip and install dependencies:

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

---

## 4. Configuring PostgreSQL

1. Install PostgreSQL 17 (Windows, from an **Administrator** PowerShell), keeping
   port 5432 and choosing a password for the `postgres` superuser:
   ```powershell
   winget install --id PostgreSQL.PostgreSQL.17 -e --interactive
   ```
2. Create the app's own database user and databases, and point `.env` at them.
   From `backend/` (after creating `.env` from `.env.example`, see section 5):
   ```powershell
   .\.venv\Scripts\python.exe scripts\setup_postgres.py
   ```
   It asks for the `postgres` password (used once, never saved), then creates a
   non-superuser role `khabarnazar_app` with a random password, the databases
   `khabarnazar` and `khabarnazar_test`, and writes `DATABASE_URL` and
   `TEST_DATABASE_URL` into `.env` after saving a timestamped `.env.backup-*`
   copy. Re-running it is safe (databases are kept; the role gets a new password).
3. Create the tables with `alembic upgrade head` (section 6).

**What is in the database:** [`docs/DATABASE.md`](docs/DATABASE.md) describes every table and
column, with a diagram, allowed values and the migration history ([`docs/schema.sql`](docs/schema.sql)
has the exact SQL). For the live state at any time (migration level, row counts, latest
activity, pending disputes) run:
```powershell
.\.venv\Scripts\python.exe scripts\describe_database.py --summary
```
After adding a migration, regenerate the docs with `scripts\describe_database.py`
(no flag); `--check` reports whether they still match the database.

By default PostgreSQL only accepts password logins from this computer, and
Windows Firewall blocks port 5432 from other devices, so the database is not
reachable from the network; the phone talks only to the FastAPI server.

*(For quick prototyping without PostgreSQL, SQLite also works:
`DATABASE_URL="sqlite:///./khabarnazar.db"`.)*

---

## 5. Environment Variables (`.env`)

Copy `.env.example` to `.env` in the `backend/` directory:

```powershell
cp .env.example .env
```

Review and adjust your environment variables:
- `DATABASE_URL` (**required**): PostgreSQL connection string. Relative SQLite
  paths are resolved from `backend/`, so the same database is used no matter
  which folder you start the server from.
- `JWT_SECRET` (**required**, at least 32 characters): generate one with
  `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
- `JWT_ALGORITHM`: Usually `HS256`.
- `ACCESS_TOKEN_EXPIRE_MINUTES`: Token validity duration (e.g. `1440` minutes / 24 hours).
- `UPLOAD_DIR`: Path to the image upload store (`uploads`, resolved from `backend/`).
- `MAX_IMAGE_PIXELS`: largest decoded image (width x height) accepted, against decompression bombs (default 40,000,000).
- `OCR_MIN_LETTERS` / `OCR_MIN_CONFIDENCE`: when OCR text counts as usable, sending the image down the
  image-with-text branch (default 10 letters, average confidence 0.3).
- `PRELOAD_MODELS`: load the AI models in a background thread at startup (default `true`).
- `MAX_UPLOAD_SIZE_MB`: Maximum permitted file upload size (default: 10 MB).
- `CORS_ORIGINS`: Allowed browser origins (e.g. Expo web `http://localhost:8081`).
  Native apps on a phone/emulator are not affected by CORS.

---

## 6. Running Alembic Migrations

The server does **not** create tables by itself; the schema is managed only by
Alembic. Run this after the first setup and after every `git pull` that adds a
migration (the server will report "no such table/column" errors otherwise):

```bash
alembic upgrade head
```

To create a new migration after updating SQLAlchemy models:

```bash
alembic revision --autogenerate -m "describe_migration"
alembic upgrade head
```

---

## 7. Starting the FastAPI Server

Start the development server with live reload:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

---

## 8. Swagger & OpenAPI Documentation

Once the server is running, explore the interactive documentation in your browser:

- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **Health Check**: [http://localhost:8000/health](http://localhost:8000/health)

To call protected endpoints in Swagger: run `POST /auth/login`, copy the
`access_token` from the response, click **Authorize**, and paste the token.

---

## 9. Running Tests

To run the automated test suite from the `backend/` directory:

```bash
pytest
```

That uses a temporary SQLite file. To run the same tests against PostgreSQL
(the `TEST_DATABASE_URL` database created by `scripts/setup_postgres.py`):

```bash
pytest --postgres
```

The PostgreSQL test database is **wiped at the start of every run**, so the
suite refuses any database whose name does not end in `_test`.

Tests use an isolated SQLite database and do not write to your development PostgreSQL instance.
The test schema is built by running the real Alembic migrations, and string
column lengths are enforced as PostgreSQL would, so length bugs show up in tests.
`tests/test_text_model.py` trains a tiny throwaway model on synthetic sentences
to test the model/explainability plumbing; its output is meaningless as news analysis.

---

## 10. Stage 3 submission endpoints

All submission routes require a Bearer JWT from `POST /auth/login` or `POST /auth/register`.

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/submissions/text` | Save text and classify it only when a compatible trained model is connected. |
| `POST` | `/submissions/image` | Upload JPEG, PNG, or WEBP (max 10 MB). Stored under `backend/uploads/` with a generated filename. |
| `GET` | `/submissions` | Current user's history, newest first (`skip`, `limit`). |
| `GET` | `/submissions/{submission_id}` | Full record for a submission owned by the current user. |

Example text body:

```json
{ "text": "Yeh Roman Urdu news claim hai." }
```

Example image upload (multipart):

```bash
curl -X POST http://localhost:8000/submissions/image ^
  -H "Authorization: Bearer YOUR_TOKEN" ^
  -F "file=@screenshot.png"
```

The API returns `text_submission.processing_status` as `completed` or `unavailable`.
When no compatible classifier is connected, it returns `Uncertain` with null
`text_confidence` and `combined_risk_score`, plus an explanation of the limitation.
It never substitutes a mock prediction.

Users can read only their own submissions; admins can read any submission.

**Risk score.** `text_confidence` is the classifier's maximum softmax score; it
is uncalibrated and does not measure factual truth. `combined_risk_score` is the
model's probability estimate that the content is *Fake*, so a
confident "Real" result has a low risk. Only a text classification (typed text, or
the text read from an image) sets `final_label` and `combined_risk_score`. The
image detector's `image_score` is never mixed in: an AI-generated picture does not
make a claim false (see "AI pipeline" below).

## Stage 4: dataset and model preparation

The root `dataset/` folders are reserved for local project data. Keep original
workbooks and images under `dataset/raw/`; the preparation scripts write derived
files to the split folders and never overwrite source files. No dataset files
were present when this pipeline was added, so column names and label values are
not assumed.

Install the added dataset/image dependencies from this directory:

```bash
pip install -r requirements.txt
```

Inspect an Excel workbook's sheets, column names, and row counts without printing
its contents:

```bash
python scripts/preprocess_excel.py ../dataset/raw/excel/your_file.xlsx --inspect
```

Prepare CSV train/validation/test splits. Specify the text column only after
checking the workbook; normalization preserves Urdu marks and removes only
excess whitespace and fully empty text rows. Exact duplicate rows and fully
empty rows are removed. Existing labels and other columns are retained as-is.

```bash
python scripts/preprocess_excel.py ../dataset/raw/excel/your_file.xlsx --text-column ACTUAL_TEXT_COLUMN --label-column ACTUAL_LABEL_COLUMN
```

With `--label-column`, rows with an empty label are removed, duplicate texts
are kept once, texts that appear with *different* labels are dropped entirely
(they cannot be learned), and the splits are stratified so every split has the
same Fake/Real proportion. The script prints how many rows each step removed and
writes the cleaned data to `dataset/processed/cleaned.csv`.

The split proportions default to 70% train, 10% validation, and 20% test, with
a fixed random seed for repeatability. Do not run this on the only copy of
important data; source files remain untouched. Generated files are written to
`dataset/train/train.csv`, `dataset/validation/validation.csv`, and
`dataset/test/test.csv`, replacing those generated split files on rerun.

### Stage 5: Urdu and Roman Urdu text models

`app/ai/text/predict.py` picks one model per input:

| Input | Model | Location | Reported score (macro-F1) |
|---|---|---|---|
| Urdu script, up to 150 words | XLM-R base, trained on Hook and Bait | `text_module/urdu/models/xlmr/` (or the older `models/text/xlmr/`) | 0.974 Hook and Bait test (release `urdu-xlmr-v1`) |
| Urdu script, longer than 150 words | word + character TF-IDF + Logistic Regression, trained on FIRE 2021 | `text_module/urdu/models/tfidf_long_articles.joblib` (in git) | 0.639 FIRE 2021 test |
| Roman Urdu | XLM-R large, trained on the KhabarNazar Roman Urdu dataset | `text_module/roman_urdu/models/xlmr/` | see `text_module/roman_urdu/README.md` |
| English, mixed script, unidentified | none | - | returns `Uncertain` |

Scores are the ones reported by the training notebooks in `text_module/`; this backend has
not re-run them (the datasets are not in the repository).

Each checkpoint gets the preprocessing it was trained with:
- **Urdu XLM-R, release `urdu-xlmr-v1`:** the notebook's `clean_urdu` (punctuation kept), up to
  256 tokens.
- **Older `text-model-v1` checkpoint:** urduhack cleaning with punctuation removed and a 64-token
  limit, read from its `khabarnazar_config.json`.
- **TF-IDF model:** the notebook's `clean_urdu`, on the whole article.
- **Roman Urdu XLM-R:** the text as typed, up to 512 tokens.

If the TF-IDF file is missing, long Urdu text goes to the XLM-R model (truncated, and the
explanation says so). Short Urdu text is never sent to the TF-IDF model, because it was trained
on full articles.

Download the XLM-R folders (about 1 GB each, git-ignored) from the repository root:

```bash
python text_module/download_models.py urdu
python text_module/download_models.py roman_urdu
```

Overrides: `KHABARNAZAR_URDU_XLMR_DIR`, `KHABARNAZAR_ROMAN_XLMR_DIR`,
`KHABARNAZAR_URDU_XLMR_MAX_LEN`, `KHABARNAZAR_ROMAN_XLMR_MAX_LEN` (the older shared
`KHABARNAZAR_XLMR_MAX_LEN` applies to Roman Urdu only), `KHABARNAZAR_TEXT_MODEL_PATH` (the
TF-IDF file) and `KHABARNAZAR_LONG_TEXT_WORDS`. A max length above a model's training limit is
rejected. The `.joblib` file must be loaded with the scikit-learn version it was saved with
(pinned in `requirements.txt`).

The authenticated `POST /submissions/text` endpoint stores the prediction in the existing
submission workflow. Model scores are classifier scores, not independent fact-checking.
`text_module/urdu/test_urdu_backend.py` runs the real Urdu routing end to end without a server.

### Stage 6: OCR and image analysis

Image submissions run EasyOCR for Urdu (`ur`) and English (`en`), then pass any
extracted text through the same supported-language text routing when a matching
trained artifact is available. OCR output, average OCR confidence, detected script/language,
extracted-text prediction, and extracted-text confidence are saved with the
submission. Apply the new database fields with:

```bash
alembic upgrade head
```

EasyOCR and its weights are loaded only when the first image is analyzed. The
first OCR request can download model weights; by default they are stored in
`backend/.cache/easyocr`. Set `KHABARNAZAR_OCR_MODEL_DIR` to choose another
location. On Windows, EasyOCR's installation guidance asks users to install
PyTorch and torchvision first using the official PyTorch selector, then install
the backend requirements. OCR is CPU-only in this backend configuration.

The AI-generated vs real image detector is described in "AI pipeline" below.
OCR lives separately in `app/ai/image/ocr.py`. OCR text analysis
does not determine whether image pixels are authentic, and image authenticity
does not determine whether a news claim is true. The service keeps those
signals separate. If EasyOCR is not installed or its weights cannot be loaded,
the submission still records a clear OCR-unavailable explanation and does not
invent a result.

To prepare an image dataset, place images under `dataset/raw/images/` (one
sub-folder per class, e.g. `authentic/` and `manipulated/`) and run:

```bash
python scripts/preprocess_images.py
```

Resized copies are written to `dataset/processed/images/` with the same folder
structure; unreadable files are listed and skipped. Originals are not modified.

`app.ai.image.preprocess.preprocess_image(source, destination)` validates JPG,
PNG, and WEBP image extensions, confirms OpenCV can decode the image, and saves
a resized copy with its aspect ratio preserved (maximum dimension 1024 by
default). This is input preparation only; it does not run OCR or infer image
authenticity or news truth.

### Stage 7: explanations

When the trained Stage 5 text model is present, API results include a JSON
string in `explainability.highlighted_words`. Each entry has a `word`, a signed
`contribution`, and a `direction` (`supports_prediction` or
`opposes_prediction`). For the TF-IDF model these come from its
weights; for the XLM-R models each word is removed in turn and the change in the
model's output is measured (up to 40 distinct words). These are feature
attributions from the model, not fact-check evidence. The explanation summary states this limitation. With no
trained model, highlights remain `null` and the API explains why.

`app.ai.image.explain.save_attribution_heatmap(...)` can render a heatmap from a
2D attribution array supplied by a future visual model. It does not create
attributions on its own. The image submission path saves a heatmap only when an
image model returns such an array; until then `heatmap_path` stays `null` and
the explanation identifies the missing visual attribution. A heatmap describes
model attention and does not establish image authenticity or claim truth.

### Lists, paging and the admin dashboard

`GET /submissions`, `GET /admin/submissions` and `GET /disputes` take `skip`
and `limit` (max 100) and return a plain JSON list, newest first. The total
number of matching rows across all pages is in the `X-Total-Count` response
header (exposed to browsers via CORS), so clients can page with
`skip = rows loaded so far` until they reach the total.

- `GET /submissions` is always the signed-in user's **own** history, admins
  included.
- `GET /disputes?mine=true` returns only your own disputes even as an admin
  (without it, admins see everyone's). `status=pending|reviewed|closed` filters
  on the server.
- `GET /admin/submissions` items add `user_email`, `dispute_count`,
  `latest_dispute_id` and `latest_dispute_status` to the normal submission.
- `GET /admin/stats` returns totals counted across the whole database: users,
  submissions (by label and by type), admin overrides, and disputes
  (total / pending / reviewed).

### Stage 8: disputes and administrator review

- `POST /disputes` accepts `submission_id`, a 10–5000 character
  `justification`, and an optional HTTP(S) `evidence_link`. Users can dispute
  only their own submissions; an existing pending dispute returns `409`.
- `GET /disputes` returns the current user's disputes. An admin sees all
  disputes. Both can use `?status=pending|reviewed|closed`, `skip`, and `limit`.
- `PATCH /disputes/{id}` is admin-only. Send `admin_decision` as `uphold_ai` or
  `override` and an `admin_comment`. An override also requires `override_label`
  (`Fake`, `Real`, or `Uncertain`) and updates the submission's final label and
  label source. A dispute can only be reviewed once.

**Failed-login limits.** After 5 wrong passwords for the same email from the
same device (or 20 across any emails from one device) within 15 minutes,
`POST /auth/login` answers `429` with a `Retry-After` header until the window
passes; a successful login clears that email's count. Adjust with
`LOGIN_MAX_FAILURES_PER_ACCOUNT`, `LOGIN_MAX_FAILURES_PER_CLIENT` and
`LOGIN_LOCKOUT_MINUTES`. The counts are kept in memory, so they reset when the
server restarts and are not shared between multiple server processes.

**App sessions.** The app keeps the login token in the iOS Keychain / Android
Keystore (`expo-secure-store`; browser storage on web). Any `401` on an
authenticated request signs the user out and shows "Session expired".

Registration always assigns the `user` role; clients cannot grant themselves
admin access by setting a role or using a special email address. To promote an
existing account from a trusted local environment, run this ORM-based command
from `backend/` after configuring `.env`:

```bash
python scripts/set_user_role.py admin@example.com admin
```

Use the same command with `user` to revoke admin access. No migration is needed
for Stage 8; the existing dispute table already has the review fields.

### Stage 9: Expo frontend connection

The Expo app's `lib/api.ts` is the shared REST client. It calls the versioned
FastAPI routes for registration, login, current user, text/image submissions,
history, disputes, admin review, and protected image display. Set
`EXPO_PUBLIC_API_URL` in `KhabarNazar_Frontend/.env` to the backend origin (the
client appends `/api/v1`):

```text
# Android emulator
EXPO_PUBLIC_API_URL=http://10.0.2.2:8000

# Physical phone: use the development computer's LAN address
EXPO_PUBLIC_API_URL=http://192.168.1.20:8000
```

Then start FastAPI from `backend/` with
`uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`, and start Expo from `KhabarNazar_Frontend/` with
`npm start`. The phone and development computer must be on the same network.
The app sends either text or an image per analysis because the backend has
separate submission endpoints. Confidence and model signals missing from the
backend are shown as unavailable rather than filled with demo scores.

Password reset and server-side profile name/email editing are not implemented
by the current API. Profile photos remain local to the device.

## AI pipeline

`app/ai/pipeline.py` implements the project diagram:

```text
Text  -> text pipeline -> text classification -----------------------------------> evaluation
Image -> image pipeline -> image with text    -> OCR -> text classification -> image pair -> evaluation
                        -> image with no text -> AI-generated or real -----------------------> evaluation
```

- **Text.** `app/ai/text/predict.py` detects the input language and routes Urdu script and Roman
  Urdu to their separate XLM-R checkpoints. Both checkpoints map class `0` to `Real` and `1` to
  `Fake`; Urdu uses its checkpoint metadata limit (64 tokens), and Roman Urdu uses its trained
  512-token limit. The tokenizer truncates beyond those limits as it did during training, and the
  response explanation says when truncation occurred. Roman Urdu text is sent to its tokenizer
  unchanged. Urdu uses the Urdu training normalization. English, mixed-script, and ambiguous Latin
  input are not routed to either checkpoint and return `Uncertain` without a score.
- **Image with text.** EasyOCR (Urdu + English) reads the image. If the text has at least
  `OCR_MIN_LETTERS` letters and average confidence `OCR_MIN_CONFIDENCE`, it goes through the *same*
  text pipeline as typed text. The image, its OCR text and the classification are stored together
  in `image_submissions` (the "image pair"), and `analysis_branch` is `image_pair`. The AI-or-real
  detector is not run, and `manipulation_prediction` is `Skipped: image has text`.
- **Image with no usable text** (none, too little, unclear, or OCR unavailable): the zero-shot
  ensemble from `image_module/` notebook 05 (CLIP ViT-L/14 + DINOv2-L + robust ResNet18, P(real)
  averaged, threshold 0.5). `image_score` is the chance the picture is AI-generated, and
  `manipulation_prediction` is `Likely AI-generated` or `Likely real photo`. The heatmap is Grad-CAM
  from the ResNet18 member. Preprocessing copies the notebooks: shorter side to 512, then a 224x224
  centre crop, so only the centre of the image is analysed. `analysis_branch` is `ai_or_real`.
- **Evaluation.** `evaluate()` does not combine branches. The verdict and risk come from the text
  classification only. On the AI-or-real branch the verdict is always `Uncertain`, because no claim
  was checked.

Every unavailable part (missing weights, missing packages, a model error) is reported in the
explanation instead of being replaced by a made-up result.

### Model files

| Model | Location | How to get it |
|---|---|---|
| Urdu XLM-RoBERTa | `models/text/xlmr/` (existing local checkpoint) or `text_module/urdu/models/xlmr/` | `python text_module/download_models.py urdu` downloads the verified `urdu-xlmr-v1` release if you need a fresh copy. |
| Roman Urdu XLM-RoBERTa-large (~1.12 GB weights) | `text_module/roman_urdu/models/xlmr/` (git-ignored) | `python text_module/download_models.py roman_urdu` downloads the `roman-urdu-xlmr-v1` release. |
| Image heads + robust ResNet18 | `image_module/models/` (in git) | comes with the repo |
| CLIP ViT-L/14, DINOv2-L (about 2.9 GB) | Hugging Face cache | downloaded automatically on first load |
| EasyOCR Urdu + English | `backend/.cache/easyocr` | downloaded automatically on first OCR |

`KHABARNAZAR_URDU_XLMR_DIR` and `KHABARNAZAR_ROMAN_XLMR_DIR` override the respective text model
folders. `KHABARNAZAR_URDU_XLMR_MAX_LEN` and `KHABARNAZAR_ROMAN_XLMR_MAX_LEN` set per-model token
limits and cannot exceed the verified training/checkpoint limits. The legacy
`KHABARNAZAR_XLMR_MAX_LEN` is a Roman Urdu override only; if it is set to `256`, Roman Urdu uses 256
tokens until that variable is removed or changed (for 512, set it to `512` or set the Roman-specific
variable). Urdu continues to use its own 64-token training limit. These values can be set in
`backend/.env`; the code does not rewrite that file. `KHABARNAZAR_IMAGE_MODEL_DIR` and
`KHABARNAZAR_OCR_MODEL_DIR` continue to override the image/OCR folders.

### Installing the ML packages (CPU)

```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
pip install urduhack --no-deps
```

Without them the API still runs and reports every model as unavailable.

### Reported results (from the module notebooks, not re-run here)

The datasets are not in the repository, so these numbers are recorded from the local
checkpoint metadata and have not been reproduced by this backend. The external result
is a warning that held-out accuracy should not be treated as general fact-checking quality.

- Urdu text, Hook and Bait test set: macro-F1 0.942, accuracy 94.4%. On Bend the Truth (outside
  data, full articles): macro-F1 0.555, close to chance. It works on headline-style text.
- Roman Urdu XLM-R large, one reported test run (826 examples): macro-F1 0.842, accuracy 84.3%.
  The source articles are LLM-transliterated rather than naturally user-written Roman Urdu; this
  backend has not reproduced those metrics. Model probabilities are uncalibrated classifier scores,
  not independent fact verification.
- Image ensemble, zero-shot: AI vs Real 94.6%, Tiny-GenImage 91.5%, Misinfo test split 84.0%
  (AUC 0.910). Source: `image_module/outputs/05_comparison.csv`.

### Tests

`pytest` mocks OCR and the models. `pytest --real-models` also runs smoke tests that load the
real models (they need the files above).
