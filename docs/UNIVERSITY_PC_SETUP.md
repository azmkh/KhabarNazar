# Setting up KhabarNazar on another PC

How to continue development on a second computer (for example the university PC) from
GitHub. Commands are for **Windows PowerShell**; on macOS/Linux use `source .venv/bin/activate`
and `.venv/bin/python` instead of `.\.venv\Scripts\python.exe`.

Git only carries **tracked files**. Secrets, model weights, your database records and uploaded
images are not in GitHub; see [Files and data not stored in GitHub](#files-and-data-not-stored-in-github).

## 1. Required software

| Software | Version used on the development PC | Notes |
|---|---|---|
| Git | any recent | |
| Python | 3.14.4 | `backend/README.md` supports 3.11 to 3.14 |
| Node.js / npm | 24.15.0 / 11.12.1 | the frontend is Expo SDK 57, React Native 0.86 |
| PostgreSQL | 17.11 | optional, see step 5 for SQLite |
| Expo Go (phone) | the build for SDK 57 | only for testing on a phone |

**Disk and memory.** About 10 GB free for the virtual environment and models:
- Urdu XLM-R: 1.1 GB.
- Roman Urdu XLM-R: 1.1 GB.
- CLIP and DINOv2 image backbones: 2.9 GB.
- EasyOCR weights: 0.3 GB.
- PyTorch: about 1 GB.

With every model loaded the backend uses about 4 to 5 GB of RAM. A GPU is not needed; the
CPU builds of PyTorch are used.

## 2. Get the code

```powershell
git clone https://github.com/azmkh/KhabarNazar
cd KhabarNazar
git status --short --branch     # expect: ## main...origin/main
```

All work is on the `main` branch. The repository root is the Expo app; the backend is in
`backend/`, and the model folders are `text_module/` and `image_module/`.
(On the first PC this same folder is named `KhabarNazar_Frontend`.)

## 3. Backend environment

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install urduhack --no-deps
```

- **Order matters:** install the CPU PyTorch build first. A plain `pip install -r requirements.txt`
  would otherwise pull a different torch build.
- **scikit-learn is pinned to 1.9.1 on purpose:** the long-article model
  `text_module/urdu/models/tfidf_long_articles.joblib` must be loaded with that version.
- **urduhack** is only used by the older Urdu checkpoint (`text-model-v1`). The current
  `urdu-xlmr-v1` release does not need it.

## 4. Backend `.env` (manual)

```powershell
copy .env.example .env
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48))"
```

Open `backend/.env` and paste the printed value into `JWT_SECRET=`. Use a **new** secret on each PC,
and never copy the first PC's `.env` into GitHub. Every other value in `.env.example` has a working
default. Set the variables below yourself:

| Variable | Required | Purpose |
|---|---|---|
| `DATABASE_URL` | yes | database the app uses (filled by step 5) |
| `TEST_DATABASE_URL` | for `pytest --postgres` | a separate database whose name ends in `_test`; it is wiped on every test run |
| `JWT_SECRET` | yes | signs login tokens; at least 32 random characters |
| `CORS_ORIGINS` | no | only for browsers (Expo web, Swagger) |
| `KHABARNAZAR_*` model settings | no | commented out in `.env.example`; the defaults are correct |

## 5. Database

**Option A: PostgreSQL (same as the first PC).** Install PostgreSQL 17 and remember the
`postgres` superuser password. Then, from `backend/`:

```powershell
.\.venv\Scripts\python.exe scripts\setup_postgres.py
```

The script:
- asks for the superuser password once, and never saves it;
- creates the role `khabarnazar_app` and the databases `khabarnazar` and `khabarnazar_test`;
- writes `DATABASE_URL` and `TEST_DATABASE_URL` into `backend/.env`, after making a backup copy.

Options include `--host`, `--port`, `--superuser`, `--app-user`, `--database` and `--test-database`.

**Option B: SQLite** (no installation, for example without admin rights on a lab PC). In
`backend/.env` set:

```text
DATABASE_URL=sqlite:///./khabarnazar.db
```

**Then, either way, create the tables:**

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe scripts\describe_database.py --summary
```

There are no seed scripts. Register an account in the app, then make it an administrator:

```powershell
.\.venv\Scripts\python.exe scripts\set_user_role.py your.email@example.com admin
```

The database schema is described in `backend/docs/DATABASE.md`.

## 6. Trained models

| Model | How it arrives | Where it goes |
|---|---|---|
| Urdu XLM-R (release `urdu-xlmr-v1`) | `download_models.py`, below | `text_module/urdu/models/xlmr/` (git-ignored) |
| Roman Urdu XLM-R (release `roman-urdu-xlmr-v1`) | `download_models.py`, below | `text_module/roman_urdu/models/xlmr/` (git-ignored) |
| Urdu long-article TF-IDF | in git | `text_module/urdu/models/tfidf_long_articles.joblib` |
| Image heads + robust ResNet18 | in git | `image_module/models/` |
| CLIP ViT-L/14, DINOv2-L | downloaded automatically from Hugging Face on first start | Hugging Face cache in your user folder |
| EasyOCR Urdu + English | downloaded automatically on the first OCR | `backend/.cache/easyocr/` (git-ignored) |

From the **repository root**:

```powershell
.\backend\.venv\Scripts\python.exe text_module\download_models.py
```

This downloads both XLM-R models (about 2.2 GB) from the public GitHub Releases. Notes:
- Give a name to download just one: `... download_models.py urdu` or `... download_models.py roman_urdu`.
- Files that are already present are skipped, so an interrupted download can simply be re-run.
- Python's standard library is enough; no GitHub login is needed.

**Check that the models load with the correct settings** (from `backend/`):

```powershell
.\.venv\Scripts\python.exe -c "from app.ai.text import xlmr; [print(s, xlmr.model_dir(s), xlmr.is_configured(s), xlmr.get_classifier(s)[0].max_len) for s in ('urdu','roman')]"
```

Expected: both lines end in `True` and the limit, which is `256` for Urdu (`urdu-xlmr-v1`) and
`512` for Roman Urdu. Each checkpoint's labels are read from its `config.json` (0 = real,
1 = fake) and checked when it loads. The length limits can be lowered, never raised, with:
- `KHABARNAZAR_URDU_XLMR_MAX_LEN` and `KHABARNAZAR_ROMAN_XLMR_MAX_LEN`;
- the older `KHABARNAZAR_XLMR_MAX_LEN`, which applies to Roman Urdu only.

See `backend/README.md`, "Stage 5", for routing and preprocessing.

> The first PC still runs the older Urdu checkpoint `text-model-v1` (in `models/text/xlmr/`), and
> its GitHub release has been removed. A new PC gets `urdu-xlmr-v1`, the team's current model.
> Results for the same Urdu sentence can therefore differ between the two PCs. Copy the old
> folder over (see the last section) only if you need identical results.

## 7. Frontend

From the repository root:

```powershell
npm ci
```

Create a file named `.env` in the repository root containing:

```text
EXPO_PUBLIC_API_URL=http://<this PC's LAN IP address>:8000
```

Find the IP with `ipconfig` (the IPv4 address of the active adapter). For the Android emulator
use `http://10.0.2.2:8000`. The app adds `/api/v1` itself.

## 8. Run the app

Backend, from `backend/`:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

- **Models:** they load in the background after startup. The first start also downloads the
  image backbones and OCR weights, so give it a few minutes.
- **Avoid `--reload`:** with it, every file change reloads all the models.
- **Firewall:** allow Python through Windows Firewall when asked, so the phone can connect.
- **Health check:** `http://localhost:8000/health` should say `healthy`, and API docs are at `/docs`.

Frontend, in a second terminal at the repository root:

```powershell
npm start
```

Scan the QR code with Expo Go. The phone and the PC must be on the same network.

## 9. Tests

From `backend/`:

```powershell
.\.venv\Scripts\python.exe -m pytest                                  # mocked models, temporary SQLite
.\.venv\Scripts\python.exe -m pytest --postgres                       # same, on TEST_DATABASE_URL (wiped)
.\.venv\Scripts\python.exe -m pytest --real-models -m real_models     # loads the real models (slow)
.\.venv\Scripts\python.exe -m alembic check                           # models match the migrations
.\.venv\Scripts\python.exe scripts\describe_database.py --check       # schema docs are up to date
```

From the repository root:

```powershell
.\backend\.venv\Scripts\python.exe -m pytest text_module\tests
.\backend\.venv\Scripts\python.exe text_module\urdu\test_urdu_backend.py   # real Urdu routing, no server
npm run typecheck
```

On the first PC (commit `06f5818`):
- the plain suite gave **122 passed, 9 skipped**;
- the real-model tests passed 9 of 9;
- the type-check was clean.

The 9 skipped tests are the real-model tests. Plain `pytest` never touches your development
database.

## 10. Troubleshooting

| Problem | Fix |
|---|---|
| `JWT_SECRET must be a random string of at least 32 characters` | Step 4: set `JWT_SECRET` in `backend/.env` |
| `pip` pulls a large CUDA torch, or torch fails to install | Install torch first with the CPU index URL (step 3) |
| `download_models.py` stops with "Incomplete download" | The connection dropped; run the same command again, and it resumes from the `.part` file |
| A result says "The trained urdu XLM-R model is unavailable or incomplete" | Run `download_models.py` (step 6); check the folder holds `config.json`, `model.safetensors` and `tokenizer.json` |
| The long-article model fails to load | Make sure `scikit-learn==1.9.1` is installed (`pip show scikit-learn`) |
| "max length must be between 3 and its trained limit" | Remove or lower the `KHABARNAZAR_*_MAX_LEN` override in `backend/.env` |
| The first image check is very slow | The CLIP/DINOv2 and EasyOCR weights download on first use; wait for the backend log to settle |
| Phone shows "Cannot reach the backend" | Check `EXPO_PUBLIC_API_URL`, restart `npm start` after editing `.env`, allow the firewall, and use the same network. University Wi-Fi often blocks device-to-device traffic, so a phone hotspot for both is a workaround |
| `pytest --postgres` refuses to run | `TEST_DATABASE_URL` must be PostgreSQL with a name ending in `_test` (re-run `setup_postgres.py`) |
| Backend uses a lot of RAM | Set `PRELOAD_MODELS=false` so models load on first use; the image models are the largest |

## 11. Daily Git workflow

```powershell
git status --short --branch          # 1. start clean, or know what is uncommitted
git fetch origin                     # 2. see what teammates pushed
git log --oneline HEAD..origin/main  #    commits you do not have yet
git pull --ff-only                   # 3. update (stops instead of merging if histories differ)
git switch -c feature/short-name     # 4. optional: a branch for bigger changes
# ... work, then run the tests (step 9)
git status
git diff                             # 5. review before staging
git add <the files you changed>      #    not "git add -A" blindly
git diff --cached                    #    check: no .env, no models, no database files
git commit -m "feat: what changed"
git push -u origin HEAD              # 6. push, then confirm with git status
```

- Never force-push, and never run `git reset --hard` or `git clean` on work you have not pushed.
- **Never commit** `.env` files, `.env.backup-*`, model weights, `*.db` files, database dumps or
  `backend/uploads/`. `.gitignore` already excludes them; keep it that way.
- If `git pull --ff-only` stops, both PCs (or a teammate) changed `main`. Run `git fetch` and then
  `git merge origin/main`, and resolve the conflicts carefully.
- **Push from one PC before switching to the other.** Git cannot sync uncommitted files, ignored
  files or database records between your PCs.

## Files and data not stored in GitHub

| Item | Needed? | How to get it on a new PC |
|---|---|---|
| `backend/.env` (database URL, JWT secret) | yes | **Recreate** (steps 4 and 5). Never transfer or commit it; it holds passwords |
| Root `.env` (`EXPO_PUBLIC_API_URL`) | yes | **Recreate** (step 7); it differs per PC and network |
| `backend/.venv`, `node_modules` | yes | **Recreate** with pip / `npm ci` |
| Urdu XLM-R `urdu-xlmr-v1`, Roman Urdu XLM-R | yes | **Download** with `text_module/download_models.py` |
| CLIP, DINOv2, EasyOCR weights | yes | **Downloaded automatically** on first use |
| Older Urdu checkpoint `text-model-v1` (`models/text/xlmr/`, 1.1 GB) | no | Only on the first PC; its release was removed. **Manual transfer** (USB drive or a private cloud folder) only if you need identical results |
| Development database records (on the first PC: 2 users, 41 submissions, 2 disputes) | no | Test data; **recreate** by using the app. If you really need it, take a `pg_dump` and move it privately. Never put it in GitHub, because it holds account emails and password hashes |
| `backend/uploads/` (images for those submissions) | no | Belongs to the database records above: move both together or neither |
| Training datasets | only for retraining | Not in the repository or on the first PC (only `.gitkeep` placeholders). The notebooks in `text_module/` and `image_module/` say where each dataset comes from |
| `KhabarNazar_Backend_Guide.pdf` (outside the repository) | no | Personal document; copy it manually if you want it |
