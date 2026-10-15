import os
from datetime import timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

class Config:
    DATABASE_EVALUATION_FILE = os.environ.get("DATABASE_EVALUATION_FILE")
    MENU_IMPORT_API_KEY = os.environ.get("MENU_IMPORT_API_KEY", "")
    SECRET_KEY = os.environ.get("SECRET_KEY")
    PASSWORD_PEPPER = os.environ.get("PASSWORD_PEPPER", "")
    MONGODB_URI = os.environ.get("MONGODB_URI")
    MONGODB_DATABASE = os.environ.get("MONGODB_DATABASE", "makanwhere")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True, "pool_recycle": 300}
    SESSION_COOKIE_NAME = "makanwhere_session"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "true").lower() == "true"
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    MAX_CONTENT_LENGTH = 64 * 1024
    SAMPLE_CATALOGUE = os.environ.get("SAMPLE_CATALOGUE", "true").lower() == "true"
    TRUST_PROXY = os.environ.get("TRUST_PROXY", "false").lower() == "true"
    RATELIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URI", "memory://")
    RATELIMIT_HEADERS_ENABLED = True
    TRUSTED_HOSTS = os.environ.get("TRUSTED_HOSTS", "makanwhere.4bytedigi.com,localhost,127.0.0.1").split(",")
