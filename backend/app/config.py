import json
from pathlib import Path
from typing import List, Union
from pydantic import field_validator
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

    # Security — required, set in .env
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    # File uploads
    UPLOAD_DIR: str = str(BASE_DIR / "uploads")
    MAX_UPLOAD_SIZE_MB: int = 10
    ALLOWED_IMAGE_TYPES: Union[List[str], str] = ["image/jpeg", "image/png", "image/webp"]

    # Weights for the combined risk score (text fake-probability vs image manipulation score)
    TEXT_RISK_WEIGHT: float = 0.7
    IMAGE_RISK_WEIGHT: float = 0.3

    # CORS
    CORS_ORIGINS: Union[List[str], str] = ["http://localhost:8081", "http://localhost:19006"]

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

    @field_validator("DATABASE_URL")
    @classmethod
    def resolve_sqlite_path(cls, v: str) -> str:
        # sqlite:///./file.db would otherwise create a new database in the current directory.
        prefix = "sqlite:///"
        if v.startswith(prefix) and not v.startswith(prefix + "/") and ":memory:" not in v:
            path = Path(v[len(prefix):])
            if not path.is_absolute():
                return prefix + (BASE_DIR / path).resolve().as_posix()
        return v

settings = Settings()
