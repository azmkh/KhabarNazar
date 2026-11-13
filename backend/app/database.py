import logging
from functools import lru_cache
from pathlib import Path
from typing import Generator, Optional
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker
from app.config import settings

# Engine setup with appropriate connection arguments
connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
    echo=False,
)

logger = logging.getLogger(__name__)

SessionLocal =sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db() -> Generator:
    """Dependency that yields a database session and closes it on finish."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_db_connection() -> dict:
    """Verifies whether database connection is active and responsive."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "connected", "database": engine.dialect.name}
    except Exception:
        # Log details server-side only; connection errors can contain hostnames or usernames.
        logger.exception("Database health check failed")
        return {"status": "disconnected", "database": engine.dialect.name}


ALEMBIC_DIR = Path(__file__).resolve().parents[1] / "alembic"


@lru_cache(maxsize=1)
def migration_head() -> Optional[str]:
    """The newest migration in backend/alembic/versions (read once per process)."""
    try:
        from alembic.script import ScriptDirectory

        return ScriptDirectory(str(ALEMBIC_DIR)).get_current_head()
    except Exception:
        logger.exception("Could not read the Alembic migration scripts")
        return None


def check_migrations() -> dict:
    """Compare the database's migration revision with the newest one in the code.

    After a `git pull` that adds a migration, the code expects columns the database does not have
    yet, and requests fail with "no such column" errors until `alembic upgrade head` is run.
    """
    head = migration_head()
    try:
        from alembic.runtime.migration import MigrationContext

        with engine.connect() as conn:
            current = MigrationContext.configure(conn).get_current_revision()
    except Exception:
        # Same as the connection check: details stay in the server log.
        logger.exception("Could not read the database migration revision")
        return {"status": "unknown", "current": None, "head": head}
    if head is None:
        status = "unknown"
    else:
        status = "up_to_date" if current == head else "behind"
    return {"status": status, "current": current, "head": head}
