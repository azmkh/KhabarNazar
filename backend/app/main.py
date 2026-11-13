import logging
import threading
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.ai.pipeline import model_warmup
from app.config import settings
from app.database import check_db_connection, check_migrations
import app.models  # ensure models are registered with Base.metadata
from app.routers import auth_router, users_router, submissions_router, disputes_router, admin_router

# The schema is managed only by Alembic (`alembic upgrade head`). Creating tables
# here would hide missing migrations and make `alembic upgrade` fail on PostgreSQL.

logger = logging.getLogger(__name__)
MIGRATION_HINT = "The database is behind the code: run `alembic upgrade head` in backend/ and restart."


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # A database left behind after `git pull` breaks requests in confusing ways; say so up front.
    migrations = check_migrations()
    if migrations["status"] == "behind":
        logger.warning("%s (database at %s, code at %s)", MIGRATION_HINT, migrations["current"], migrations["head"])
    # Models take seconds to load (and download on first run); do it off the request path.
    # Requests that arrive earlier simply wait for the same one-time load.
    if settings.PRELOAD_MODELS:
        threading.Thread(target=model_warmup, name="model-warmup", daemon=True).start()
    yield


app = FastAPI(
    lifespan=lifespan,
    title=settings.PROJECT_NAME,
    version=settings.PROJECT_VERSION,
    description=settings.PROJECT_DESCRIPTION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Configure CORS. Only browsers (Expo web, Swagger on another origin) need this;
# native Expo apps are not subject to CORS. Auth uses Bearer headers, not cookies,
# so credentials are not allowed.
origins = settings.CORS_ORIGINS

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins if isinstance(origins, list) else [origins],
    allow_credentials=False,
    # Browsers hide non-standard headers unless listed; the web app reads list totals from this one.
    expose_headers=["X-Total-Count"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(SQLAlchemyError)
async def database_error(_request: Request, exc: SQLAlchemyError):
    """Database errors are 500s, except the common case of a database not yet migrated after a
    `git pull`: then say exactly what to do (the app shows `detail` in its error message)."""
    if check_migrations()["status"] == "behind":
        logger.error("Request failed because the database is behind the code: %s", type(exc).__name__)
        return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content={"detail": MIGRATION_HINT})
    logger.error("Database error", exc_info=exc)
    return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"detail": "Internal server error"})


@app.get("/", tags=["Root"])
def root():
    """Root endpoint welcoming users and pointing to API documentation."""
    return {
        "project": settings.PROJECT_NAME,
        "version": settings.PROJECT_VERSION,
        "description": settings.PROJECT_DESCRIPTION,
        "status": "online",
        "docs_url": "/docs",
        "health_url": "/health",
    }


@app.get("/health", tags=["Health"])
def health_check():
    """Health check endpoint monitoring system and database availability."""
    db_status = check_db_connection()
    migrations = check_migrations() if db_status.get("status") == "connected" else None
    is_healthy = db_status.get("status") == "connected" and migrations["status"] != "behind"

    payload = {
        "status": "healthy" if is_healthy else "degraded",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": settings.PROJECT_VERSION,
        "environment": settings.ENVIRONMENT,
        "database": db_status,
    }
    if migrations is not None:
        payload["migrations"] = migrations
        if migrations["status"] == "behind":
            payload["message"] = MIGRATION_HINT

    status_code = status.HTTP_200_OK if is_healthy else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(status_code=status_code, content=payload)


# Include authentication, user, and submission routers
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(submissions_router)
app.include_router(disputes_router)
app.include_router(admin_router)

# Also expose under versioned API prefix for standard REST clients
if settings.API_V1_STR:
    app.include_router(auth_router, prefix=settings.API_V1_STR)
    app.include_router(users_router, prefix=settings.API_V1_STR)
    app.include_router(submissions_router, prefix=settings.API_V1_STR)
    app.include_router(disputes_router, prefix=settings.API_V1_STR)
    app.include_router(admin_router, prefix=settings.API_V1_STR)

