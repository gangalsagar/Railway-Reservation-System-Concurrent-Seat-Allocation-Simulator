import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

class Config:
    """Base application configuration."""
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-railway-key-change-in-prod")
    DB_NAME = os.environ.get("DB_NAME", "railway_reservation.db")
    DATABASE_PATH = BASE_DIR / DB_NAME
    TESTING = False
    DEBUG = False

class DevelopmentConfig(Config):
    """Development environment configuration."""
    DEBUG = True

class TestingConfig(Config):
    """Testing environment configuration."""
    TESTING = True
    DB_NAME = "test_railway_reservation.db"
    DATABASE_PATH = BASE_DIR / "tests" / "test_railway_reservation.db"

class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    TESTING = False

config_by_name = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}

