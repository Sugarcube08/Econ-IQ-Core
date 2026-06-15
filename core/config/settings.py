import os
from pathlib import Path

from dotenv import load_dotenv

# Get the project root directory (econiq/backend)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Manually load .env
load_dotenv(os.path.join(PROJECT_ROOT, ".env"), override=False)

# Force POLARS_MAX_THREADS to 1 by default, or to whatever is in the env/settings
os.environ["POLARS_MAX_THREADS"] = os.getenv("POLARS_MAX_THREADS", "1")

from pydantic import Field  # noqa: E402
from pydantic_settings import BaseSettings, SettingsConfigDict  # noqa: E402


class Settings(BaseSettings):
    # App
    APP_NAME: str = "econiq Intelligence Backend"
    APP_ENV: str = "development"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    WORKERS: int = 1

    # Postgres
    POSTGRES_URL: str = Field(..., validation_alias="POSTGRES_URL")
    POSTGRES_POOL_SIZE: int = 10
    POSTGRES_MAX_OVERFLOW: int = 20
    POSTGRES_TIMEOUT: int = 30
    ENABLE_PERSISTENT_STATE: bool = True

    # RG Semantics
    ENABLE_RG_SEMANTIC_CLASSIFICATION: bool = True
    CUSTOMER_RG_WEIGHT: float = 1.0
    GENUINE_RG_WEIGHT: float = 1.0
    UNKNOWN_RG_WEIGHT: float = 0.8

    # Cadence
    CADENCE_MIN_EVENTS: int = 3
    CADENCE_STDDEV_MULTIPLIER: float = 1.5

    # Redis
    REDIS_URL: str | None = Field(None, validation_alias="REDIS_URL")
    REDIS_DB: int = 0
    REDIS_TIMEOUT: int = 5

    # Auth & JWT (EdDSA Keys)
    JWT_ALGORITHM: str = "EdDSA"
    JWT_PRIVATE_KEY: str | None = Field(None, validation_alias="JWT_PRIVATE_KEY")
    JWT_PUBLIC_KEY: str | None = Field(None, validation_alias="JWT_PUBLIC_KEY")
    JWT_ACCESS_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_EXPIRE_DAYS: int = 7
    JWT_ISSUER: str = "econiq.intelligence"
    JWT_AUDIENCE: str = "econiq.api"

    # SMTP
    SMTP_HOST: str = Field("localhost", validation_alias="SMTP_HOST")
    SMTP_PORT: int = Field(1025, validation_alias="SMTP_PORT")
    SMTP_USERNAME: str | None = Field(None, validation_alias="SMTP_USERNAME")
    SMTP_PASSWORD: str | None = Field(None, validation_alias="SMTP_PASSWORD")
    SMTP_FROM_EMAIL: str = Field("no-reply@econiq.intelligence", validation_alias="SMTP_FROM_EMAIL")
    SMTP_USE_TLS: bool = Field(False, validation_alias="SMTP_USE_TLS")

    # Feature Toggles
    EMAIL_SERVICE: bool = Field(True, validation_alias="EMAIL_SERVICE")
    ENABLE_BACKGROUND_WORKERS: bool = Field(True, validation_alias="ENABLE_BACKGROUND_WORKERS")
    STARTUP_MODE: str = Field("full", validation_alias="STARTUP_MODE")
    SKIP_SCHEMA_VERIFICATION: bool = Field(False, validation_alias="SKIP_SCHEMA_VERIFICATION")

    # Worker Tuning
    INTELLIGENCE_POLL_INTERVAL: int = Field(15, validation_alias="INTELLIGENCE_POLL_INTERVAL")
    SYNC_POLL_INTERVAL: int = Field(30, validation_alias="SYNC_POLL_INTERVAL")
    POLARS_MAX_THREADS: int = Field(1, validation_alias="POLARS_MAX_THREADS")
    SYNC_BATCH_SIZE: int = Field(500, validation_alias="SYNC_BATCH_SIZE")
    INTELLIGENCE_CHUNK_SIZE: int = Field(10, validation_alias="INTELLIGENCE_CHUNK_SIZE")
    RECOMPUTE_BATCH_SIZE: int = Field(10, validation_alias="RECOMPUTE_BATCH_SIZE")

    # Security Policies
    OTP_PEPPER: str | None = Field(None, validation_alias="OTP_PEPPER")
    API_KEY_PEPPER: str | None = Field(None, validation_alias="API_KEY_PEPPER")
    REFRESH_TOKEN_PEPPER: str | None = Field(None, validation_alias="REFRESH_TOKEN_PEPPER")

    # Rate Limiting (Burst / Sustained)
    AUTH_RATE_LIMIT_LOGIN_BURST: str = "5/minute"
    AUTH_RATE_LIMIT_LOGIN_SUSTAINED: str = "20/day"
    AUTH_RATE_LIMIT_OTP_RESEND: str = "1/minute"

    # Observability
    ENABLE_METRICS: bool = True
    ENABLE_TRACING: bool = True
    ENABLE_AUDIT_LOGGING: bool = True

    model_config = SettingsConfigDict(
        env_file=os.path.join(PROJECT_ROOT, ".env"), env_file_encoding="utf-8", extra="ignore", case_sensitive=True
    )

    def validate_production(self):
        """Strict validation for production mode."""
        if self.APP_ENV == "production":
            required = [
                "REDIS_URL",
                "JWT_PRIVATE_KEY",
                "JWT_PUBLIC_KEY",
                "OTP_PEPPER",
                "API_KEY_PEPPER",
                "REFRESH_TOKEN_PEPPER",
            ]
            for field in required:
                if getattr(self, field) is None:
                    raise ValueError(f"CRITICAL: {field} must be set in production")


settings = Settings()
# In production, we call settings.validate_production() in main.py startup
