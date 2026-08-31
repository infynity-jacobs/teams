import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "Lead CRM"
    FRONTEND_DIR: str = os.getenv("FRONTEND_DIR", "/opt/leadcrm/frontend")
    ENV: str = os.getenv("ENV", "production")

    # Database - defaults to a local SQLite file for quick evaluation.
    # For production on Ubuntu 22.04, set DATABASE_URL to a PostgreSQL DSN, e.g.:
    # postgresql+psycopg2://leadcrm:changeme@localhost:5432/leadcrm
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./leadcrm.db")

    # JWT
    SECRET_KEY: str = os.getenv("SECRET_KEY", "CHANGE_ME_IN_PRODUCTION_" + os.urandom(8).hex())
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480"))

    # CORS - comma separated list of allowed origins
    CORS_ORIGINS: str = os.getenv("CORS_ORIGINS", "*")

    # Initial super admin bootstrap (only used on first run / empty DB)
    BOOTSTRAP_ADMIN_USERNAME: str = os.getenv("BOOTSTRAP_ADMIN_USERNAME", "admin")
    BOOTSTRAP_ADMIN_PASSWORD: str = os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "ChangeMe123!")
    BOOTSTRAP_ADMIN_EMAIL: str = os.getenv("BOOTSTRAP_ADMIN_EMAIL", "admin@example.com")

    class Config:
        env_file = ".env"


settings = Settings()
