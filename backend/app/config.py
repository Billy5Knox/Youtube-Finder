import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

class Settings:
    GOOGLE_CLIENT_ID: str = os.environ.get("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET: str = os.environ.get("GOOGLE_CLIENT_SECRET", "")
    GOOGLE_REDIRECT_URI: str = os.environ.get("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/callback")
    DATABASE_PATH: str = os.environ.get("DATABASE_PATH", str(BASE_DIR / "youtube_finder.db"))
    SECRET_KEY: str = os.environ.get("SECRET_KEY", "change-me-in-production")
    FRONTEND_URL: str = os.environ.get("FRONTEND_URL", "http://localhost:5173")

settings = Settings()
