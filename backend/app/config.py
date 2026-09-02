import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "Lead CRM"
    ENV: str = os.getenv("ENV", "production")

    # Database - defaults to a local SQLite file for quick evaluation.
    # For production on Ubuntu 22.04, set DATABASE_URL to a PostgreSQL DSN, e.g.:
    # postgresql+psycopg2://leadcrm:changeme@localhost:5432/leadcrm
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./leadcrm.db")

    # JWT
    SECRET_KEY: str = os.getenv("SECRET_KEY", "CHANGE_ME_IN_PRODUCTION_" + os.urandom(8).hex())
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480"))
    PASSWORD_RESET_EXPIRE_MINUTES: int = int(os.getenv("PASSWORD_RESET_EXPIRE_MINUTES", "30"))

    # CORS - comma separated list of allowed origins
    CORS_ORIGINS: str = os.getenv("CORS_ORIGINS", "*")

    # Initial super admin bootstrap (only used on first run / empty DB)
    BOOTSTRAP_ADMIN_USERNAME: str = os.getenv("BOOTSTRAP_ADMIN_USERNAME", "admin")
    BOOTSTRAP_ADMIN_PASSWORD: str = os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "ChangeMe123!")
    BOOTSTRAP_ADMIN_EMAIL: str = os.getenv("BOOTSTRAP_ADMIN_EMAIL", "admin@example.com")

    # NOTE: FRONTEND_DIR is intentionally NOT declared here - main.py reads
    # it directly via os.getenv() since it's only needed at static-file-mount
    # time, not as part of app configuration. `extra="ignore"` below is what
    # actually matters: without it, pydantic-settings treats ANY key present
    # in .env that isn't declared as a field above as a fatal validation
    # error and refuses to start the app at all - which is exactly what
    # happens with the FRONTEND_DIR line that install_ubuntu22.sh writes
    # into backend/.env. Keep this permissive so unrelated/future keys in
    # .env never take the whole app down.
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()

