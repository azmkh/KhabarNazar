"""Describe the KhabarNazar database: what is in it, and what each part means.

Reads the structure straight from the database in DATABASE_URL (so tables,
columns, types, keys and indexes are always exact) and combines it with the
plain-English descriptions below. Run from backend/:

    .\\.venv\\Scripts\\python.exe scripts\\describe_database.py            # (re)write docs/DATABASE.md + docs/schema.sql
    .\\.venv\\Scripts\\python.exe scripts\\describe_database.py --summary  # live status: migration, row counts, activity
    .\\.venv\\Scripts\\python.exe scripts\\describe_database.py --check    # exit 1 if the docs no longer match the database

Only structure and counts are read; no row contents (emails, texts, hashes)
are ever printed or written. Passwords in DATABASE_URL are masked.
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import MetaData, create_engine, inspect, text
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine import make_url
from sqlalchemy.schema import CreateIndex, CreateTable

from app.config import settings

BACKEND_DIR = Path(__file__).resolve().parents[1]
DOCS_DIR = BACKEND_DIR / "docs"
MARKDOWN = DOCS_DIR / "DATABASE.md"
SCHEMA_SQL = DOCS_DIR / "schema.sql"

# ── What everything means ───────────────────────────────────────────────────────
# Every table and column in the database must be described here; the script and
# tests/test_database_docs.py report anything missing, so the docs cannot drift.
TABLES: dict[str, dict] = {
    "users": {
        "purpose": "Registered accounts. One row per person who can sign in.",
        "columns": {
            "id": "Unique account number, assigned automatically.",
            "name": "Display name, 2–100 characters (leading/trailing spaces removed).",
            "email": "Login email, stored in lower case. Unique: two accounts can never share one.",
            "password_hash": "bcrypt hash of the password (never the password itself). Never sent to the app.",
            "role": "`user` or `admin`. New accounts are always `user`; only `scripts/set_user_role.py` changes it.",
            "created_at": "When the account was created (UTC).",
            "updated_at": "When the account row last changed (UTC); updated automatically.",
        },
    },
    "submissions": {
        "purpose": (
            "One row per check a user runs (text or image). This is the parent record that holds the "
            "outcome shown to the user; the details live in `text_submissions` or `image_submissions`, "
            "and the reasons in `explainability`."
        ),
        "columns": {
            "id": "Unique check number, assigned automatically. Used in app links such as `/result/42`.",
            "user_id": "The account that ran the check. Deleting the account deletes its checks.",
            "submission_type": "`text` or `image` (`both` is reserved and not used yet).",
            "detected_language": "Language of the text, or of the text read from the image: `urdu`, `roman_urdu`, `english`, `mixed` or `unknown`. Empty if there was no text.",
            "is_news": "Whether the content is news. Empty until a news/non-news classifier is connected (never guessed).",
            "news_confidence": "Confidence of that news/non-news decision, 0–1. Empty until the classifier exists.",
            "combined_risk_score": "Estimated chance the content is fake, 0–1: the text model's probability of Fake (weight 0.7) combined with the image score (weight 0.3), using only the signals that exist. Empty when no model produced a signal.",
            "final_label": "The verdict shown to the user: `Fake`, `Real` or `Uncertain`. An admin override replaces the AI's label.",
            "final_label_source": "Who set `final_label`: `AI` or `Admin`.",
            "admin_comment": "Comment from the most recent admin review of this check, if any.",
            "created_at": "When the check was run (UTC).",
        },
    },
    "text_submissions": {
        "purpose": "The text that was checked, and the text model's result. Exactly one per text check.",
        "columns": {
            "id": "Unique row number, assigned automatically.",
            "submission_id": "The check this text belongs to (one-to-one). Deleted with the check.",
            "input_text": "The text as submitted, 3–10,000 characters.",
            "detected_language": "`urdu`, `roman_urdu`, `english`, `mixed` or `unknown`.",
            "text_prediction": "The text model's label: `Fake`, `Real` or `Uncertain` (`Uncertain` while no model is trained).",
            "text_confidence": "How sure the model is of its own label, 0–1. This is not the risk score. Empty while no model is trained.",
            "created_at": "When the row was saved (UTC).",
        },
    },
    "image_submissions": {
        "purpose": (
            "The uploaded image and its results. Exactly one per image check. The two image signals are "
            "kept separate on purpose: text read from the image (OCR + text model) and whether the "
            "image itself looks manipulated."
        ),
        "columns": {
            "id": "Unique row number, assigned automatically.",
            "submission_id": "The check this image belongs to (one-to-one). Deleted with the check.",
            "image_path": "File name of the stored image inside `backend/uploads/` (a random name, never the user's). The image file itself is not in the database.",
            "original_filename": "The file name on the user's device, kept for display only (max 255 characters).",
            "mime_type": "Image type detected from the file's contents: `image/jpeg`, `image/png` or `image/webp`.",
            "file_size_bytes": "Size of the uploaded file in bytes (maximum 10 MB).",
            "ocr_text": "Text read from the image by OCR. Empty if OCR is not installed or found no text.",
            "ocr_confidence": "Average OCR confidence for that text, 0–1.",
            "detected_language": "Language of the OCR text (same values as for text checks).",
            "text_prediction": "The text model's label for the OCR text, if there was text: `Fake`, `Real` or `Uncertain`.",
            "text_confidence": "How sure the text model is of that label, 0–1. Empty while no model is trained.",
            "image_score": "Image manipulation / AI-generated score, 0–1. Empty until an image model is connected.",
            "manipulation_prediction": "Short label from the image model (max 50 characters). Currently `Not Analyzed`.",
            "created_at": "When the row was saved (UTC).",
        },
    },
    "explainability": {
        "purpose": "Why the result came out as it did. Exactly one per check.",
        "columns": {
            "id": "Unique row number, assigned automatically.",
            "submission_id": "The check this explanation belongs to (one-to-one). Deleted with the check.",
            "highlighted_words": "JSON text: a list of `{word, contribution, direction}` showing which words pushed the text model's score. Empty when no model is trained. These are model attributions, not fact-checks.",
            "heatmap_path": "Heatmap image inside `backend/uploads/` (`explanations/<id>_heatmap.png`). Empty unless an image model supplies one.",
            "explanation_summary": "Plain-language summary shown on the result screen, including what was unavailable and why.",
            "model_version": "Which analysis produced the result, e.g. `text-tfidf-logreg`, `text-model-unavailable`, `easyocr-ur-en`, `ocr-unavailable`.",
            "created_at": "When the row was saved (UTC).",
        },
    },
    "disputes": {
        "purpose": (
            "A user challenging a verdict, and the admin's decision. A check can be disputed more than "
            "once (only one may be pending at a time)."
        ),
        "columns": {
            "id": "Unique dispute number, assigned automatically.",
            "submission_id": "The check being disputed. Deleted with the check.",
            "user_id": "The account that filed the dispute (always the check's owner). Deleted with the account.",
            "justification": "The user's reason, 10–5,000 characters.",
            "evidence_link": "Optional http(s) link to supporting evidence (max 512 characters).",
            "status": "`pending` until an admin decides, then `reviewed`. (`closed` is accepted as a filter but not set by the app.)",
            "admin_decision": "`uphold_ai` (keep the AI verdict) or `override` (replace it). Empty while pending.",
            "admin_comment": "The admin's required comment explaining the decision.",
            "override_label": "With `override`: the new verdict, `Fake`, `Real` or `Uncertain`. Copied to `submissions.final_label`.",
            "reviewed_at": "When the admin decided (UTC). Empty while pending.",
            "created_at": "When the dispute was filed (UTC).",
        },
    },
    "alembic_version": {
        "purpose": "Bookkeeping for Alembic, the migration tool: one row holding the migration revision this database is at.",
        "columns": {"version_num": "The current migration revision ID (compare with the migration history below)."},
    },
}

# Relationship labels for the diagram, keyed by (child table, foreign-key column).
RELATIONSHIP_LABELS = {
    ("submissions", "user_id"): "runs",
    ("disputes", "user_id"): "files",
    ("text_submissions", "submission_id"): "text details",
    ("image_submissions", "submission_id"): "image details",
    ("explainability", "submission_id"): "explained by",
    ("disputes", "submission_id"): "disputed by",
}

ALLOWED_VALUES = [
    ("users.role", "`user`, `admin`"),
    ("submissions.submission_type", "`text`, `image` (`both` reserved)"),
    ("submissions.final_label, text_submissions.text_prediction, image_submissions.text_prediction", "`Fake`, `Real`, `Uncertain`"),
    ("submissions.final_label_source", "`AI`, `Admin`"),
    ("*.detected_language", "`urdu`, `roman_urdu`, `english`, `mixed`, `unknown`"),
    ("image_submissions.mime_type", "`image/jpeg`, `image/png`, `image/webp`"),
    ("disputes.status", "`pending`, `reviewed` (`closed` reserved)"),
    ("disputes.admin_decision", "`uphold_ai`, `override`"),
    ("disputes.override_label", "`Fake`, `Real`, `Uncertain`"),
]

TABLE_ORDER = ["users", "submissions", "text_submissions", "image_submissions", "explainability", "disputes", "alembic_version"]


# ── Reading the database ────────────────────────────────────────────────────────

def safe_url() -> str:
    return make_url(settings.DATABASE_URL).render_as_string(hide_password=True)


def type_name(column_type) -> str:
    name = str(column_type)
    if name.startswith("TIMESTAMP") and getattr(column_type, "timezone", False):
        return "TIMESTAMPTZ"
    return name.replace("DOUBLE PRECISION", "DOUBLE PRECISION")


def migration_history() -> tuple[list[tuple[str, str]], str]:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    script = ScriptDirectory.from_config(config)
    revisions = list(reversed(list(script.walk_revisions())))
    return [(r.revision, (r.doc or "").strip().splitlines()[0]) for r in revisions], script.get_current_head()


def read_schema(engine):
    inspector = inspect(engine)
    tables = {}
    for name in inspector.get_table_names():
        pk = set(inspector.get_pk_constraint(name)["constrained_columns"])
        fks = inspector.get_foreign_keys(name)
        uniques = inspector.get_unique_constraints(name)
        unique_columns = {u["column_names"][0] for u in uniques if len(u["column_names"]) == 1}
        indexes = inspector.get_indexes(name)
        unique_columns |= {i["column_names"][0] for i in indexes if i["unique"] and len(i["column_names"]) == 1}
        columns = []
        for column in inspector.get_columns(name):
            keys = []
            if column["name"] in pk:
                keys.append("PK")
            for fk in fks:
                if column["name"] in fk["constrained_columns"]:
                    keys.append(f"FK → {fk['referred_table']}.{fk['referred_columns'][0]}")
            if column["name"] in unique_columns and column["name"] not in pk:
                keys.append("UNIQUE")
            columns.append({
                "name": column["name"],
                "type": type_name(column["type"]),
                "nullable": column["nullable"],
                "default": str(column["default"]) if column.get("default") else "",
                "keys": keys,
            })
        tables[name] = {"columns": columns, "fks": fks, "indexes": indexes, "unique_columns": unique_columns, "pk": pk}
    return tables


def missing_descriptions(tables) -> list[str]:
    problems = []
    for name, info in tables.items():
        described = TABLES.get(name)
        if not described:
            problems.append(f"table {name} has no description")
            continue
        for column in info["columns"]:
            if column["name"] not in described["columns"]:
                problems.append(f"column {name}.{column['name']} has no description")
        for column in described["columns"]:
            if column not in {c["name"] for c in info["columns"]}:
                problems.append(f"description for {name}.{column} but the database has no such column")
    for name in TABLES:
        if name not in tables:
            problems.append(f"description for table {name} but the database has no such table")
    return problems


# ── Writing the documents ──────────────────────────────────────────────────────

def mermaid(tables) -> str:
    lines = ["erDiagram"]
    for name in [t for t in TABLE_ORDER if t in tables and t != "alembic_version"]:
        for fk in tables[name]["fks"]:
            column = fk["constrained_columns"][0]
            one_to_one = column in tables[name]["unique_columns"]
            arrow = "||--o|" if one_to_one else "||--o{"
            label = RELATIONSHIP_LABELS.get((name, column), column)
            lines.append(f'    {fk["referred_table"]} {arrow} {name} : "{label}"')
    for name in [t for t in TABLE_ORDER if t in tables and t != "alembic_version"]:
        lines.append(f"    {name} {{")
        for column in tables[name]["columns"]:
            kind = column["type"].split("(")[0].replace(" ", "_").lower()
            marks = " ".join(k for k in ("PK", "FK", "UK") if (k == "PK" and "PK" in column["keys"])
                             or (k == "FK" and any(x.startswith("FK") for x in column["keys"]))
                             or (k == "UK" and "UNIQUE" in column["keys"]))
            lines.append(f"        {kind} {column['name']}{(' ' + marks.replace(' ', ', ')) if marks else ''}")
        lines.append("    }")
    return "\n".join(lines)


def markdown(tables, server_version: str, revision: str, history, head: str) -> str:
    out = []
    add = out.append
    add("# KhabarNazar database schema")
    add("")
    add("> **Generated file.** Do not edit by hand. After changing the database (a new Alembic migration), run")
    add("> `.\\.venv\\Scripts\\python.exe scripts\\describe_database.py` from `backend/` to regenerate it.")
    add("> For the database's live state (row counts, latest activity) run the same script with `--summary`.")
    add("")
    add("| | |")
    add("|---|---|")
    add(f"| Database | PostgreSQL {server_version} (`khabarnazar`; tests use `khabarnazar_test`) |")
    add(f"| Migration revision | `{revision}` {'(latest)' if revision == head else f'(**behind**: latest is `{head}`)'} |")
    add(f"| Tables | {len([t for t in tables if t != 'alembic_version'])} application tables + `alembic_version` |")
    add("| Managed by | SQLAlchemy models in `backend/app/models/`, changed only through Alembic migrations in `backend/alembic/versions/` |")
    add("")
    add("## How the tables fit together")
    add("")
    add("Every check a user runs creates **one `submissions` row** (the outcome) plus exactly one details row "
        "(**`text_submissions`** *or* **`image_submissions`**) and one **`explainability`** row (the reasons). "
        "**`disputes`** are added later if the user challenges the verdict. Deleting a user deletes their checks and "
        "disputes; deleting a check deletes its details, explanation and disputes (`ON DELETE CASCADE`).")
    add("")
    add("```mermaid")
    add(mermaid(tables))
    add("```")
    add("")
    add("Diagram key: `||--o{` one-to-many, `||--o|` one-to-(zero or one). PK primary key, FK foreign key, UK unique.")
    add("")
    add("## Tables")
    add("")
    for name in [t for t in TABLE_ORDER if t in tables] + sorted(set(tables) - set(TABLE_ORDER)):
        info = tables[name]
        described = TABLES.get(name, {"purpose": "**No description yet.**", "columns": {}})
        add(f"### `{name}`")
        add("")
        add(described["purpose"])
        add("")
        add("| Column | Type | Null? | Key | Meaning |")
        add("|---|---|---|---|---|")
        for column in info["columns"]:
            meaning = described["columns"].get(column["name"], "**No description yet.**")
            key = ", ".join(column["keys"])
            add(f"| `{column['name']}` | {column['type']} | {'yes' if column['nullable'] else 'no'} | {key} | {meaning} |")
        add("")
        fks = info["fks"]
        if fks:
            add("**Links:** " + "; ".join(
                f"`{fk['constrained_columns'][0]}` → `{fk['referred_table']}.{fk['referred_columns'][0]}`"
                f" (on delete: {(fk.get('options') or {}).get('ondelete', 'no action').lower()})" for fk in fks))
            add("")
        indexes = [i for i in info["indexes"]]
        if indexes:
            add("**Indexes:** " + "; ".join(
                f"`{i['name']}` ({', '.join(i['column_names'])}{', unique' if i['unique'] else ''})" for i in indexes))
            add("")
    add("## Allowed values")
    add("")
    add("These columns are plain text in the database; the API (Pydantic schemas and services) only ever writes these values.")
    add("")
    add("| Column | Values |")
    add("|---|---|")
    for column, values in ALLOWED_VALUES:
        add(f"| `{column}` | {values} |")
    add("")
    add("## Notes")
    add("")
    add("- **Times** are stored as `TIMESTAMPTZ` (with time zone) and written in UTC; the app converts them to the phone's local time.")
    add("- **Files are not stored in the database.** Uploaded images and heatmaps live in `backend/uploads/`; the database keeps only their file names.")
    add("- **Empty means \"not evaluated\".** Scores and labels that need an AI model stay empty (NULL) until that model is connected; nothing is invented.")
    add("- **Secrets:** `password_hash` is a one-way bcrypt hash. The database password itself lives only in `backend/.env`.")
    add("- The `ix_<table>_id` indexes duplicate the primary-key indexes (they come from `index=True` on the models' `id` columns). They are harmless.")
    add("")
    add("## Migration history")
    add("")
    add("Applied in this order by `alembic upgrade head`:")
    add("")
    add("| # | Revision | What it did |")
    add("|---|---|---|")
    for number, (rev, message) in enumerate(history, start=1):
        add(f"| {number} | `{rev}` | {message} |")
    add("")
    add("## Useful commands (from `backend/`)")
    add("")
    add("| Task | Command |")
    add("|---|---|")
    add("| Live status (migration level, row counts, latest activity) | `.\\.venv\\Scripts\\python.exe scripts\\describe_database.py --summary` |")
    add("| Bring the database up to date | `.\\.venv\\Scripts\\python.exe -m alembic upgrade head` |")
    add("| Which migration is the database at? | `.\\.venv\\Scripts\\python.exe -m alembic current` |")
    add("| Do the models match the migrations? | `.\\.venv\\Scripts\\python.exe -m alembic check` |")
    add("| Regenerate this document and `schema.sql` | `.\\.venv\\Scripts\\python.exe scripts\\describe_database.py` |")
    add("| Is this document still accurate? | `.\\.venv\\Scripts\\python.exe scripts\\describe_database.py --check` |")
    add("")
    add("The exact SQL that creates every table and index is in [`schema.sql`](schema.sql).")
    add("")
    return "\n".join(out)


def schema_sql(engine, revision: str) -> str:
    metadata = MetaData()
    metadata.reflect(bind=engine)
    dialect = postgresql.dialect()
    parts = [
        "-- KhabarNazar database schema (PostgreSQL). Generated by scripts/describe_database.py - do not edit by hand.",
        f"-- Matches migration revision {revision}. The database is created and changed with Alembic",
        "-- (`alembic upgrade head`); this file is a readable reference, not the way to build the database.",
        "",
    ]
    for name in [t for t in TABLE_ORDER if t in metadata.tables] + sorted(set(metadata.tables) - set(TABLE_ORDER)):
        table = metadata.tables[name]
        parts.append(str(CreateTable(table).compile(dialect=dialect)).strip() + ";")
        for index in sorted(table.indexes, key=lambda i: i.name or ""):
            parts.append(str(CreateIndex(index).compile(dialect=dialect)).strip() + ";")
        parts.append("")
    return "\n".join(parts)


def summary(engine, revision: str, head: str) -> None:
    print(f"Database:   {safe_url()}")
    with engine.connect() as connection:
        if engine.dialect.name == "postgresql":
            print(f"Server:     PostgreSQL {connection.execute(text('show server_version')).scalar()}")
            size = connection.execute(text("select pg_size_pretty(pg_database_size(current_database()))")).scalar()
            print(f"Size:       {size}")
        print(f"Migration:  {revision} {'(latest)' if revision == head else f'BEHIND - latest is {head}: run alembic upgrade head'}")
        print()
        print(f"{'table':<20} {'rows':>8}   latest row (UTC)")
        for name in [t for t in TABLE_ORDER if t != "alembic_version"]:
            rows = connection.execute(text(f"select count(*) from {name}")).scalar()
            latest = connection.execute(text(f"select max(created_at) from {name}")).scalar()
            # PostgreSQL returns time-zone-aware values in the server's zone; show them in UTC.
            if latest is not None and latest.tzinfo is not None:
                latest = latest.astimezone(timezone.utc)
            latest_text = latest.strftime("%Y-%m-%d %H:%M") if latest else "-"
            print(f"{name:<20} {rows:>8}   {latest_text}")
        print()
        admins = connection.execute(text("select count(*) from users where role = 'admin'")).scalar()
        pending = connection.execute(text("select count(*) from disputes where status = 'pending'")).scalar()
        labels = connection.execute(text("select final_label, count(*) from submissions group by final_label order by 2 desc")).all()
        print(f"Admins: {admins}   Pending disputes: {pending}   Verdicts: " + (", ".join(f"{label} {count}" for label, count in labels) or "none yet"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--summary", action="store_true", help="print the live state of the database")
    mode.add_argument("--check", action="store_true", help="exit 1 if docs/DATABASE.md or docs/schema.sql are out of date")
    args = parser.parse_args()

    engine = create_engine(settings.DATABASE_URL)
    history, head = migration_history()
    with engine.connect() as connection:
        has_version = "alembic_version" in inspect(connection).get_table_names()
        revision = connection.execute(text("select version_num from alembic_version")).scalar() if has_version else "(none)"
        server_version = connection.execute(text("show server_version")).scalar() if engine.dialect.name == "postgresql" else engine.dialect.name

    if args.summary:
        summary(engine, revision, head)
        return

    if engine.dialect.name != "postgresql":
        sys.exit("Generate the schema docs from the PostgreSQL database (DATABASE_URL points elsewhere).")

    tables = read_schema(engine)
    problems = missing_descriptions(tables)
    for problem in problems:
        print(f"WARNING: {problem} - add it to TABLES in scripts/describe_database.py", file=sys.stderr)

    new_markdown = markdown(tables, server_version, revision, history, head)
    new_sql = schema_sql(engine, revision)
    if args.check:
        stale = [p.name for p, content in ((MARKDOWN, new_markdown), (SCHEMA_SQL, new_sql))
                 if not p.exists() or p.read_text(encoding="utf-8") != content]
        if stale or problems:
            sys.exit(f"Database docs are out of date ({', '.join(stale) or 'missing descriptions'}); run scripts/describe_database.py")
        print("Database docs match the database.")
        return

    DOCS_DIR.mkdir(exist_ok=True)
    MARKDOWN.write_text(new_markdown, encoding="utf-8")
    SCHEMA_SQL.write_text(new_sql, encoding="utf-8")
    print(f"Wrote {MARKDOWN.relative_to(BACKEND_DIR)} and {SCHEMA_SQL.relative_to(BACKEND_DIR)} "
          f"({len(tables)} tables, revision {revision}).")
    if problems:
        sys.exit(1)


if __name__ == "__main__":
    main()
