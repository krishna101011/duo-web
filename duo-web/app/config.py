"""Application configuration loaded from the environment."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")


class Settings:
    """Small environment-backed settings object.

    Keeping settings in one module makes future deployment configuration easy
    to swap without scattering environment reads throughout the application.
    """

    APP_ENV = os.getenv("APP_ENV", "development")
    APP_SECRET_KEY = os.getenv("APP_SECRET_KEY", "dev-only-change-me")
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./duo_tracker.db")
    HOST = os.getenv("HOST", "127.0.0.1")
    PORT = int(os.getenv("PORT", "8000"))
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
    AI_DEFAULT_PROVIDER = os.getenv("AI_DEFAULT_PROVIDER", "OpenAI")
    AI_DEFAULT_BASE_URL = os.getenv("AI_DEFAULT_BASE_URL", "https://api.openai.com/v1")
    AI_DEFAULT_MODEL = os.getenv("AI_DEFAULT_MODEL", "gpt-5-mini")
    AI_DEFAULT_KEY = os.getenv("AI_DEFAULT_KEY", "")
    # SQLite database backups are server-wide, so regular tracker members cannot
    # manage/restore them in a multi-tracker deployment unless an admin explicitly enables it.
    ALLOW_GLOBAL_BACKUPS = os.getenv("ALLOW_GLOBAL_BACKUPS", "false").lower() in {"1", "true", "yes"}

    STATIC_DIR = ROOT_DIR / "app" / "static"
    TEMPLATE_DIR = ROOT_DIR / "app" / "templates"
    UPLOAD_DIR = ROOT_DIR / "app" / "uploads"
    BACKUP_DIR = ROOT_DIR


settings = Settings()
settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
(settings.BACKUP_DIR / "backups").mkdir(parents=True, exist_ok=True)
