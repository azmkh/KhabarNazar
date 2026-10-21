# KhabarNazar — Backend Service

Welcome to the backend service for **KhabarNazar**, an AI-assisted fake-news and misinformation detection platform for Urdu and Roman Urdu news and news images.

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

1. Ensure your PostgreSQL service is installed and running.
2. Create a dedicated database and user (or use default `postgres`):
   ```sql
   CREATE DATABASE khabarnazar;
   CREATE USER khabarnazar_user WITH ENCRYPTED PASSWORD 'your_secure_password';
   GRANT ALL PRIVILEGES ON DATABASE khabarnazar TO khabarnazar_user;
   ```
3. Set your connection string format:
   ```
   postgresql+psycopg://khabarnazar_user:your_secure_password@localhost:5432/khabarnazar
   ```
   *(Note: For local prototyping without PostgreSQL running, SQLite is also supported via `sqlite:///./khabarnazar.db`)*

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
- `TEXT_RISK_WEIGHT` / `IMAGE_RISK_WEIGHT`: weights for the combined risk score (default 0.7 / 0.3).
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
| `POST` | `/submissions/text` | Save Urdu / Roman Urdu text. AI prediction is a stub until Stage 5. |
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

`final_label` is `Uncertain` until the text model is trained. The API does not
invent predictions: while no model is connected, `text_confidence`,
`combined_risk_score`, and `is_news` are `null` (not `0` or `true`).

Users can read only their own submissions; admins can read any submission.

**Risk score.** `text_confidence` is how sure the model is of its own label;
`combined_risk_score` is the probability that the content is *Fake*, so a
confident "Real" result has a low risk. When an image manipulation model is
connected, its `image_score` is combined with the text risk using
`TEXT_RISK_WEIGHT`/`IMAGE_RISK_WEIGHT`; missing signals are left out.

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

### Stage 5: text model

The text classifier uses word and character TF-IDF features with logistic
regression. Word features cover Urdu and Roman Urdu tokens; character features
help with spelling variation in transliterated Urdu. Training data must already
contain real binary labels. The label strings are supplied explicitly so the
script does not guess their meaning.

From `backend/`, after preparing the workbook splits and confirming the actual
column and label values:

```bash
python scripts/train_text_model.py --text-column ACTUAL_TEXT_COLUMN --label-column ACTUAL_LABEL_COLUMN --fake-label ACTUAL_FAKE_VALUE --real-label ACTUAL_REAL_VALUE
```

The script evaluates against validation and test splits and writes
`models/text/text_classifier.joblib`. The API loads that file automatically;
set `KHABARNAZAR_TEXT_MODEL_PATH` to use a different artifact path. Until a
trained artifact exists, API results remain `Uncertain` with `is_stub: true`.
Only train on data you are authorized to use, and inspect the reported test
metrics before presenting this model as reliable.

### Stage 6: OCR and image analysis

Image submissions run EasyOCR for Urdu (`ur`) and English (`en`), then pass any
extracted text through the Stage 5 classifier when its trained artifact is
available. OCR output, average OCR confidence, detected script/language,
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

No trained image manipulation model is included, so `image_score` remains
`null` and `manipulation_prediction` is `Not Analyzed`. To connect one, return
`image_score`, `manipulation_prediction` (max 50 characters, e.g. `Manipulated`
or `Authentic`), and optionally `attribution_map` from `analyze_image()` in
`app/ai/image/predict.py`. OCR lives separately in `app/ai/image/ocr.py`. OCR text analysis
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
`opposes_prediction`). These are feature attributions from the model, not
fact-check evidence. The explanation summary states this limitation. With no
trained model, highlights remain `null` and the API explains why.

`app.ai.image.explain.save_attribution_heatmap(...)` can render a heatmap from a
2D attribution array supplied by a future visual model. It does not create
attributions on its own. The image submission path saves a heatmap only when an
image model returns such an array; until then `heatmap_path` stays `null` and
the explanation identifies the missing visual attribution. A heatmap describes
model attention and does not establish image authenticity or claim truth.

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

## Urdu transformer text model

Urdu-script text is classified by an XLM-RoBERTa model trained in `text_module/` (see its README).
`app/ai/text/predict.py` uses it automatically when `models/text/xlmr/` contains the trained model; otherwise
it falls back to the TF-IDF model above, or to `Uncertain`. Roman Urdu and English always use the TF-IDF path.

To enable it in this backend environment:

```bash
pip install torch --index-url https://download.pytorch.org/whl/cu128   # use the command from pytorch.org
pip install -r requirements.txt
pip install urduhack --no-deps
```

`KHABARNAZAR_TEXT_TRANSFORMER_DIR` overrides the model folder. `tests/test_text_transformer.py` tests the
routing with a fake model, so it needs neither torch nor the model files.
