"""One-time PostgreSQL setup for KhabarNazar.

Run after installing PostgreSQL, from the backend/ folder:

    .\\.venv\\Scripts\\python.exe scripts\\setup_postgres.py

It asks for the password of the PostgreSQL superuser ("postgres", chosen in
the installer). That password is only used for this connection and is never
saved. The script then:

1. creates (or updates) a dedicated login role for the app, with a new random
   password, so the backend never runs as the superuser;
2. creates the main database and a separate test database owned by that role;
3. points DATABASE_URL (and TEST_DATABASE_URL, used by `pytest --postgres`) in
   backend/.env at them, after saving a timestamped backup of the old .env.

Passwords are never printed. Re-running it is safe: existing databases are
kept, and the app role just gets a fresh password written to .env.
"""
from __future__ import annotations

import argparse
import getpass
import re
import secrets
import shutil
import sys
from datetime import datetime
from pathlib import Path

import psycopg
from psycopg import sql

BACKEND_DIR = Path(__file__).resolve().parents[1]
ENV_FILE = BACKEND_DIR / ".env"


def set_env_values(path: Path, values: dict[str, str]) -> None:
    """Replace or append KEY=value lines, leaving every other line untouched."""
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    remaining = dict(values)
    for index, line in enumerate(lines):
        match = re.match(r"\s*([A-Z_][A-Z0-9_]*)\s*=", line)
        if match and match.group(1) in remaining:
            key = match.group(1)
            lines[index] = f'{key}="{remaining.pop(key)}"'
    for key, value in remaining.items():
        lines.append(f'{key}="{value}"')
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=5432)
    parser.add_argument("--superuser", default="postgres")
    parser.add_argument("--app-user", default="khabarnazar_app")
    parser.add_argument("--database", default="khabarnazar")
    parser.add_argument("--test-database", default="khabarnazar_test")
    args = parser.parse_args()

    if not args.test_database.endswith("_test"):
        parser.error("--test-database must end with '_test' (the test suite wipes it)")

    superuser_password = getpass.getpass(f'Password for PostgreSQL user "{args.superuser}": ')
    app_password = secrets.token_urlsafe(24)

    try:
        connection = psycopg.connect(
            host=args.host, port=args.port, user=args.superuser,
            password=superuser_password, dbname="postgres", autocommit=True,
        )
    except psycopg.OperationalError as exc:
        sys.exit(f"Could not connect to PostgreSQL at {args.host}:{args.port} as {args.superuser}: {exc}")

    with connection:
        role = sql.Identifier(args.app_user)
        exists = connection.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (args.app_user,)).fetchone()
        statement = "ALTER ROLE {} WITH LOGIN PASSWORD {}" if exists else "CREATE ROLE {} WITH LOGIN PASSWORD {}"
        connection.execute(sql.SQL(statement).format(role, sql.Literal(app_password)))
        print(f"{'Updated' if exists else 'Created'} database role {args.app_user}")

        for name in (args.database, args.test_database):
            found = connection.execute("SELECT 1 FROM pg_database WHERE datname = %s", (name,)).fetchone()
            if found:
                connection.execute(sql.SQL("ALTER DATABASE {} OWNER TO {}").format(sql.Identifier(name), role))
                print(f"Database {name} already exists (kept, owner set to {args.app_user})")
            else:
                connection.execute(sql.SQL("CREATE DATABASE {} OWNER {} ENCODING 'UTF8'").format(sql.Identifier(name), role))
                print(f"Created database {name}")

    def url(database: str) -> str:
        return f"postgresql+psycopg://{args.app_user}:{app_password}@{args.host}:{args.port}/{database}"

    if ENV_FILE.exists():
        backup = ENV_FILE.with_name(f".env.backup-{datetime.now():%Y%m%d-%H%M%S}")
        shutil.copy2(ENV_FILE, backup)
        print(f"Saved the previous .env as {backup.name}")
    set_env_values(ENV_FILE, {"DATABASE_URL": url(args.database), "TEST_DATABASE_URL": url(args.test_database)})
    print("Updated DATABASE_URL and TEST_DATABASE_URL in backend/.env (passwords not shown).")
    print("Next: .\\.venv\\Scripts\\python.exe -m alembic upgrade head")


if __name__ == "__main__":
    main()
