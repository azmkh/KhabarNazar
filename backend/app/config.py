import json
from pathlib import Path
from typing import List, Union
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Base backend directory
BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    PROJECT_NAME: str = "KhabarNazar Backend"
    PROJECT_VERSION: str = "1.0.0"
    PROJECT_DESCRIPTION: str = "Fake news and misinformation detection platform for Urdu and Roman Urdu"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    API_V1_STR: str = "/api/v1"

    # Database — required, set in .env (no credentials are hard-coded here)
    DATABASE_URL: str
    # Optional direct (non-pooled) URL for Alembic migrations. Neon's pooled "-pooler" host runs
    # PgBouncer in transaction mode, which migrations should not use. Empty = DATABASE_URL.
    MIGRATION_DATABASE_URL: str | None = None
    # Connection pool per server process (PostgreSQL only). Neon's free plan is small, so keep it small.
    DB_POOL_SIZE: int = Field(default=5, ge=1)
    DB_MAX_OVERFLOW: int = Field(default=5, ge=0)
    # Recycle connections before an idle database (Neon scales to zero after 5 minutes) drops them.
    DB_POOL_RECYCLE_SECONDS: int = Field(default=300, ge=-1)

    # Security — required, set in .env
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    # Failed-login limits (per device+email, and per device across all emails)
    LOGIN_MAX_FAILURES_PER_ACCOUNT: int = 5
    LOGIN_MAX_FAILURES_PER_CLIENT: int = 20
    LOGIN_LOCKOUT_MINUTES: int = 15

    # Checks (text/image analysis) one signed-in user may run; 0 disables a limit.
    CHECK_RATE_LIMIT_PER_MINUTE: int = Field(default=10, ge=0)
    CHECK_RATE_LIMIT_PER_HOUR: int = Field(default=100, ge=0)

    # Behind a hosting proxy (Modal) every request comes from the proxy's address. When true, the
    # client address for the login limiter is read from X-Forwarded-For. Never enable this when
    # clients can reach the server directly, or they could spoof the header.
    TRUST_PROXY_HEADERS: bool = False

    # File uploads
    UPLOAD_DIR: str = str(BASE_DIR / "uploads")
    MAX_UPLOAD_SIZE_MB: int = 10
    ALLOWED_IMAGE_TYPES: Union[List[str], str] = ["image/jpeg", "image/png", "image/webp"]

    # Largest decoded image (width x height) accepted; guards against decompression bombs
    MAX_IMAGE_PIXELS: int = 40_000_000

    # Image pipeline routing: OCR text counts as "usable" (image-with-text branch) only when it
    # has at least this many letters and this average OCR confidence (0-1). Otherwise the image
    # goes to the AI-generated vs real branch.
    OCR_MIN_LETTERS: int = 10
    OCR_MIN_CONFIDENCE: float = 0.3

    # Load the text, OCR and image models in a background thread at startup, so the first
    # request does not wait for them.
    PRELOAD_MODELS: bool = True

    # Text model paths/limits. The legacy shared max-length variable is retained as a
    # Roman Urdu override; the Urdu checkpoint keeps its own training limit (64 tokens).
    XLMR_MAX_LEN: int | None = Field(default=None, gt=0, validation_alias="KHABARNAZAR_XLMR_MAX_LEN")
    URDU_XLMR_MAX_LEN: int | None = Field(default=None, gt=0, validation_alias="KHABARNAZAR_URDU_XLMR_MAX_LEN")
    ROMAN_XLMR_MAX_LEN: int | None = Field(default=None, gt=0, validation_alias="KHABARNAZAR_ROMAN_XLMR_MAX_LEN")
    URDU_XLMR_DIR: str | None = Field(default=None, validation_alias="KHABARNAZAR_URDU_XLMR_DIR")
    ROMAN_XLMR_DIR: str | None = Field(default=None, validation_alias="KHABARNAZAR_ROMAN_XLMR_DIR")
    # Urdu text longer than this many words goes to the long-article TF-IDF model
    # (text_module/urdu/models/tfidf_long_articles.joblib unless TEXT_MODEL_PATH is set).
    LONG_TEXT_WORDS: int = Field(default=150, gt=0, validation_alias="KHABARNAZAR_LONG_TEXT_WORDS")
    TEXT_MODEL_PATH: str | None = Field(default=None, validation_alias="KHABARNAZAR_TEXT_MODEL_PATH")

    # CORS
    CORS_ORIGINS: Union[List[str], str] = ["http://localhost:8081", "http://localhost:19006"]
    # Optional regex for extra browser origins, e.g. EAS Hosting preview URLs:
    # ^https://khabarnazar(--[a-z0-9-]+)?\.expo\.app$
    CORS_ORIGIN_REGEX: str | None = None

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    @field_validator("ALLOWED_IMAGE_TYPES", "CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_list(cls, v: Union[List[str], str]) -> List[str]:
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return parsed
            except Exception:
                pass
            return [i.strip() for i in v.split(",") if i.strip()]
        return v

    @field_validator("JWT_SECRET")
    @classmethod
    def validate_jwt_secret(cls, v: str) -> str:
        if len(v) < 32 or v.startswith("CHANGE_THIS"):
            raise ValueError("JWT_SECRET must be a random string of at least 32 characters")
        return v

    @field_validator("UPLOAD_DIR")
    @classmethod
    def resolve_upload_dir(cls, v: str) -> str:
        # Relative paths are relative to backend/, not to wherever uvicorn was started.
        path = Path(v).expanduser()
        return str(path if path.is_absolute() else (BASE_DIR / path).resolve())

    @field_validator("DATABASE_URL", "MIGRATION_DATABASE_URL")
    @classmethod
    def resolve_sqlite_path(cls, v: str | None) -> str | None:
        # sqlite:///./file.db would otherwise create a new database in the current directory.
        if not v:
            return v or None
        prefix = "sqlite:///"
        if v.startswith(prefix) and not v.startswith(prefix + "/") and ":memory:" not in v:
            path = Path(v[len(prefix):])
            if not path.is_absolute():
                return prefix + (BASE_DIR / path).resolve().as_posix()
        return v

settings = Settings()
