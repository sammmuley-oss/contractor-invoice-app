"""Application configuration using Pydantic Settings."""

import os
from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    APP_NAME: str = "Contractor Invoice Management"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str = "sqlite:///./contractor_invoices.db"

    # File uploads
    UPLOAD_DIR: str = str(Path(__file__).parent.parent / "uploads")
    EXPORT_DIR: str = str(Path(__file__).parent.parent / "exports")
    BACKUP_DIR: str = str(Path(__file__).parent.parent / "backups")
    MAX_UPLOAD_SIZE_MB: int = 10
    ALLOWED_EXTENSIONS: list[str] = [".pdf", ".jpg", ".jpeg", ".png", ".xlsx", ".xls"]

    # CORS
    CORS_ORIGINS: list[str] = ["*"]

    # Pagination
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()

# Ensure directories exist
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
os.makedirs(settings.EXPORT_DIR, exist_ok=True)
os.makedirs(settings.BACKUP_DIR, exist_ok=True)
