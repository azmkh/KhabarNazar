"""Start a throwaway KhabarNazar backend for the full test pass.

    python tests/full_pass/start_test_server.py --run-dir RUN --db sqlite:RUN/test.db --port 8001
    python tests/full_pass/start_test_server.py --run-dir RUN --db postgres --port 8001   # khabarnazar_test, wiped first

It builds the schema with the real Alembic migrations (a fresh SQLite file, or the *_test
PostgreSQL database after DROP OWNED), points UPLOAD_DIR at RUN/uploads, uses a throwaway JWT
secret, loads the real models at startup, and runs uvicorn in the foreground with its log in
RUN/server.log. It writes RUN/startup.json with the time until /health answered, until all models
were loaded, and until a first real text check succeeded. The real `khabarnazar` database is never used.

Rate limits: --limits raised (bulk runs; 1000/min, 100000/h) or real (the branch defaults, TC-RL).
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fp_common import BACKEND, CORS_TEST_REGEX, PY, TEST_JWT_SECRET, resolve_db  # noqa: E402


def wipe_postgres(url: str) -> None:
    from sqlalchemy import create_engine, text

    engine = create_engine(url)
    with engine.begin() as conn:
        conn.execute(text("DROP OWNED BY CURRENT_USER"))
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS public"))
    engine.dispose()


def probe(base: str, t0: float, out: Path) -> None:
    result = {}
    client = httpx.Client(timeout=10)
    while time.time() - t0 < 900:
        try:
            r = client.get(base + "/health")
            if "health_ok_s" not in result and r.status_code in (200, 503):
                result["health_ok_s"] = round(time.time() - t0, 1)
            if r.status_code == 200 and r.json().get("models", {}).get("ready"):
                result["models_ready_s"] = round(time.time() - t0, 1)
                break
        except httpx.HTTPError:
            pass
        time.sleep(1)
    try:
        email = f"startup.probe.{int(t0)}@example.com"
        tok = client.post(base + "/api/v1/auth/register", json={"name": "Startup Probe", "email": email, "password": "Password123!"}).json()["access_token"]
        r = httpx.post(base + "/api/v1/submissions/text", json={"text": "حکومت نے آج نئی سڑک کا افتتاح کیا"},
                       headers={"Authorization": f"Bearer {tok}"}, timeout=300)
        result["first_text_check_status"] = r.status_code
        result["first_text_check_done_s"] = round(time.time() - t0, 1)
    except Exception as exc:  # recorded, not hidden
        result["first_text_check_error"] = repr(exc)
    out.write_text(json.dumps(result, indent=1), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--db", required=True, help="sqlite:<path> or postgres")
    ap.add_argument("--port", type=int, default=8001)
    ap.add_argument("--limits", choices=("raised", "real"), default="raised")
    ap.add_argument("--lockout-minutes", type=int, default=15)
    ap.add_argument("--no-probe", action="store_true")
    ap.add_argument("--host", default="127.0.0.1", help="0.0.0.0 to also accept the PC's LAN address (TC-LOG-14)")
    args = ap.parse_args()

    run = Path(args.run_dir).resolve()
    run.mkdir(parents=True, exist_ok=True)
    uploads = run / "uploads"
    if uploads.exists():
        shutil.rmtree(uploads)
    uploads.mkdir()
    url = resolve_db(args.db)
    if args.db == "postgres":
        wipe_postgres(url)
    else:
        Path(url[len("sqlite:///"):]).unlink(missing_ok=True)

    env = {k: v for k, v in os.environ.items() if not k.startswith("KHABARNAZAR_")}
    env.update({
        "DATABASE_URL": url, "UPLOAD_DIR": str(uploads), "JWT_SECRET": TEST_JWT_SECRET,
        "ENVIRONMENT": "full-pass", "PRELOAD_MODELS": "true", "PYTHONUTF8": "1",
        "CORS_ORIGINS": '["http://localhost:8081", "http://localhost:8082", "http://localhost:19006"]',
        "CORS_ORIGIN_REGEX": CORS_TEST_REGEX, "LOGIN_LOCKOUT_MINUTES": str(args.lockout_minutes),
        "TRUST_PROXY_HEADERS": "false",
    })
    if args.limits == "raised":
        env.update({"CHECK_RATE_LIMIT_PER_MINUTE": "1000", "CHECK_RATE_LIMIT_PER_HOUR": "100000"})
    else:
        env.pop("CHECK_RATE_LIMIT_PER_MINUTE", None)
        env.pop("CHECK_RATE_LIMIT_PER_HOUR", None)

    subprocess.run([str(PY), "-m", "alembic", "upgrade", "head"], cwd=BACKEND, env=env, check=True,
                   capture_output=True)
    (run / "server_info.json").write_text(json.dumps({
        "db": "postgres khabarnazar_test (TEST_DATABASE_URL)" if args.db == "postgres" else url,
        "uploads": str(uploads), "port": args.port, "limits": args.limits,
        "lockout_minutes": args.lockout_minutes, "started": time.strftime("%Y-%m-%d %H:%M:%S"),
    }, indent=1), encoding="utf-8")

    t0 = time.time()
    log = open(run / "server.log", "w", encoding="utf-8")
    proc = subprocess.Popen([str(PY), "-m", "uvicorn", "app.main:app", "--host", args.host, "--port", str(args.port)],
                            cwd=BACKEND, env=env, stdout=log, stderr=subprocess.STDOUT)
    (run / "server.pid").write_text(str(proc.pid))
    if not args.no_probe:
        threading.Thread(target=probe, args=(f"http://127.0.0.1:{args.port}", t0, run / "startup.json"), daemon=True).start()
    print(f"server pid {proc.pid} on port {args.port}; log {run / 'server.log'}", flush=True)
    proc.wait()


if __name__ == "__main__":
    main()
