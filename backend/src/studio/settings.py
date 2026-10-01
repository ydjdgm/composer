from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_ROOT / ".env", extra="ignore")

    database_url: str = "postgresql+psycopg://composer:change-me@127.0.0.1:5432/composer"
    asset_root: Path = BACKEND_ROOT.parent / ".data" / "assets"
    provider_mode: Literal["fake"] = "fake"
    allowed_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    max_upload_bytes: int = Field(100 * 1024 * 1024, ge=1, le=1024 * 1024 * 1024)
    max_references: int = Field(10, ge=1, le=100)
    max_audio_seconds: float = Field(600, gt=0, le=3600)
    media_timeout_seconds: float = Field(60, gt=0, le=600)
    ffmpeg: str = "ffmpeg"
    ffprobe: str = "ffprobe"
    worker_poll_seconds: float = Field(1, ge=0.1, le=60)
    lease_seconds: int = Field(120, ge=30, le=3600)

    @field_validator("database_url")
    @classmethod
    def postgres_only(cls, value: str) -> str:
        if not value.startswith("postgresql+psycopg://"):
            raise ValueError("DATABASE_URL must use postgresql+psycopg")
        return value

    @field_validator("asset_root")
    @classmethod
    def absolute_root(cls, value: Path) -> Path:
        return (BACKEND_ROOT / value).resolve() if not value.is_absolute() else value.resolve()


@lru_cache
def settings() -> Settings:
    return Settings()
