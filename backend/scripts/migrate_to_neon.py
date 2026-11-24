"""Copy the local PostgreSQL database (schema + data) to Neon, then verify it.

Run from the backend/ folder after putting Neon's connection strings in backend/.env.neon
(git-ignored; see DEPLOYMENT.md):

    .\\.venv\\Scripts\\python.exe scripts\\migrate_to_neon.py            # copy + verify
    .\\.venv\\Scripts\\python.exe scripts\\migrate_to_neon.py --verify   # only compare row counts

Source: DATABASE_URL in backend/.env (your local database; it is only read).
Target: MIGRATION_DATABASE_URL in the target file (Neon's DIRECT host, without "-pooler"),
or its DATABASE_URL when no direct URL is given.

What it runs, with the PostgreSQL 17 client tools:

    pg_dump    --format=custom --no-owner --no-acl  (local)  -> a temporary dump file
    pg_restore --no-owner --no-acl --exit-on-error  (dump)   -> Neon

then compares every table's row count and the Alembic revision on both sides. The target must
be empty (a fresh Neon database), so nothing there is ever overwritten. Connection details are
passed to the tools through PG* environment variables; no password is printed or put on a
command line, and the dump file is deleted at the end.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from dotenv import dotenv_values
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import URL, make_url

BACKEND_DIR = Path(__file__).resolve().parents[1]


def find_tool(name: str) -> str:
    found = shutil.which(name)
    if found:
        return found
    for candidate in sorted(Path(r"C:\Program Files\PostgreSQL").glob(f"*/bin/{name}.exe"), reverse=True):
        return str(candidate)
    sys.exit(f"{name} was not found. Install the PostgreSQL 17 client tools or add their bin folder to PATH.")


def load_url(env_file: Path, *keys: str) -> URL:
    if not env_file.is_file():
        sys.exit(f"{env_file} does not exist.")
    values = dotenv_values(env_file)
    for key in keys:
        if values.get(key):
            url = make_url(values[key])
            if not url.drivername.startswith("postgresql"):
                sys.exit(f"{key} in {env_file.name} is not a PostgreSQL URL.")
            return url
    sys.exit(f"None of {', '.join(keys)} is set in {env_file.name}.")


def libpq_env(url: URL) -> dict:
    """PG* variables for pg_dump/pg_restore, so the password never appears in a command line."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("PG")}
    env.update({
        "PGHOST": url.host or "localhost",
        "PGPORT": str(url.port or 5432),
        "PGUSER": url.username or "",
        "PGPASSWORD": url.password or "",
        "PGDATABASE": url.database or "",
    })
    for key, value in url.query.items():
        if key == "sslmode":
            env["PGSSLMODE"] = str(value)
        elif key == "channel_binding":
            env["PGCHANNELBINDING"] = str(value)
    if (url.host or "").endswith(".neon.tech"):
        env.setdefault("PGSSLMODE", "require")
    return env


def describe(url: URL) -> str:
    return f"{url.database} on {url.host}"


def table_counts(url: URL) -> tuple[dict[str, int], str | None]:
    engine = create_engine(url.set(drivername="postgresql+psycopg"), connect_args=(
        {"sslmode": "require"} if (url.host or "").endswith(".neon.tech") and "sslmode" not in url.query else {}
    ))
    try:
        with engine.connect() as conn:
            tables = inspect(conn).get_table_names(schema="public")
            counts = {t: conn.execute(text(f'SELECT count(*) FROM public."{t}"')).scalar_one() for t in sorted(tables)}
            revision = None
            if "alembic_version" in tables:
                revision = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
        return counts, revision
    finally:
        engine.dispose()


def verify(source: URL, target: URL) -> bool:
    source_counts, source_rev = table_counts(source)
    target_counts, target_rev = table_counts(target)
    ok = True
    print(f"\n{'table':<28}{'local':>10}{'neon':>10}")
    for table in sorted(set(source_counts) | set(target_counts)):
        a, b = source_counts.get(table), target_counts.get(table)
        mark = "" if a == b else "   <-- differs"
        ok &= a == b
        print(f"{table:<28}{str(a):>10}{str(b):>10}{mark}")
    print(f"\nAlembic revision: local {source_rev}, neon {target_rev}")
    ok &= source_rev == target_rev
    print("Verification passed." if ok else "Verification FAILED: see the differences above.")
    return ok


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--target-env", default=".env.neon", help="file with Neon's URLs (default: .env.neon)")
    parser.add_argument("--verify", action="store_true", help="only compare row counts; copy nothing")
    args = parser.parse_args()

    source = load_url(BACKEND_DIR / ".env", "DATABASE_URL")
    target_file = Path(args.target_env)
    target = load_url(target_file if target_file.is_absolute() else BACKEND_DIR / target_file,
                      "MIGRATION_DATABASE_URL", "DATABASE_URL")
    if (source.host, source.port, source.database) == (target.host, target.port, target.database):
        sys.exit("Source and target are the same database.")
    if "-pooler" in (target.host or ""):
        print("Note: using the POOLED host for the restore; the direct host (MIGRATION_DATABASE_URL) is recommended.")
    print(f"Source: {describe(source)}\nTarget: {describe(target)}")

    if args.verify:
        return 0 if verify(source, target) else 1

    existing, _ = table_counts(target)
    if existing:
        sys.exit(f"The target already has tables ({', '.join(existing)}). Use an empty Neon database, "
                 "or run with --verify to compare.")

    pg_dump, pg_restore = find_tool("pg_dump"), find_tool("pg_restore")
    with tempfile.TemporaryDirectory(prefix="khabarnazar-neon-") as tmp:
        dump_file = Path(tmp) / "khabarnazar.dump"
        print("Dumping the local database...")
        subprocess.run([pg_dump, "--format=custom", "--no-owner", "--no-acl", f"--file={dump_file}"],
                       env=libpq_env(source), check=True)
        print(f"Dump size: {dump_file.stat().st_size / 1024:.0f} KiB. Restoring into Neon...")
        subprocess.run([pg_restore, "--no-owner", "--no-acl", "--exit-on-error", "--single-transaction",
                        f"--dbname={target.database}", str(dump_file)],
                       env=libpq_env(target), check=True)
    return 0 if verify(source, target) else 1


if __name__ == "__main__":
    sys.exit(main())
