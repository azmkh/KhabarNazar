"""The schema docs (scripts/describe_database.py) must describe every table and column."""
import sys
from pathlib import Path

from sqlalchemy import create_engine

import app.models  # noqa: F401  (registers every model on Base.metadata)
from app.config import settings
from app.database import Base

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import describe_database as docs  # noqa: E402


def test_every_model_column_is_described():
    missing = [
        f"{table.name}.{column.name}"
        for table in Base.metadata.sorted_tables
        for column in table.columns
        if column.name not in docs.TABLES.get(table.name, {}).get("columns", {})
    ]
    assert not missing, f"describe these in scripts/describe_database.py TABLES: {missing}"


def test_descriptions_match_the_migrated_database():
    # The test database is built by the real migrations, so this also catches a
    # migration that adds or drops a column without the docs being updated.
    engine = create_engine(settings.DATABASE_URL)
    try:
        problems = docs.missing_descriptions(docs.read_schema(engine))
    finally:
        engine.dispose()
    assert problems == []
