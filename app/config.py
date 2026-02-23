"""
Application configuration settings.
All secrets must be provided via environment variables / .env file.
Defaults here are safe for local development ONLY.
"""
import os
from functools import lru_cache
from typing import List
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # ── Application ───────────────────────────────────────────────────────────
    APP_NAME:    str  = "Threat Intelligence Platform"
    APP_VERSION: str  = "1.0.0"
    DEBUG:       bool = False
    LOG_LEVEL:   str  = "INFO"  # Logging level: DEBUG, INFO, WARNING, ERROR
    API_PREFIX:  str  = "/api/v1"
    ENVIRONMENT: str  = os.getenv("ENVIRONMENT", "development")

    # ── Server ────────────────────────────────────────────────────────────────
    HOST:    str = "0.0.0.0"
    PORT:    int = 8000
    WORKERS: int = 4

    # ── CORS ──────────────────────────────────────────────────────────────────
    # Comma-separated list, e.g. "https://app.mycompany.com,chrome-extension://..."
    CORS_ORIGINS: str = os.getenv("CORS_ORIGINS", "*")

    # ── Database ──────────────────────────────────────────────────────────────
    POSTGRES_USER:     str = os.getenv("POSTGRES_USER",     "postgres")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "postgres1234")
    POSTGRES_DB:       str = os.getenv("POSTGRES_DB",       "threat_intel")
    DATABASE_URL:      str = os.getenv(
        "DATABASE_URL",
        f"postgresql+asyncpg://"
        f"{os.getenv('POSTGRES_USER', 'postgres')}:"
        f"{os.getenv('POSTGRES_PASSWORD', 'postgres1234')}"
        f"@localhost:5432/"
        f"{os.getenv('POSTGRES_DB', 'threat_intel')}",
    )
    DATABASE_POOL_SIZE:    int = 10
    DATABASE_MAX_OVERFLOW: int = 20

    # ── Redis ─────────────────────────────────────────────────────────────────
    REDIS_URL:       str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    REDIS_CACHE_TTL: int = 3600   # seconds (1 hour)

    # ── JWT Security ──────────────────────────────────────────────────────────
    SECRET_KEY:                str = os.getenv("SECRET_KEY", "CHANGE_ME_IN_PRODUCTION_32_CHARS_MIN")
    ALGORITHM:                 str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # ── Fernet Encryption (for PII fields at rest) ────────────────────────────
    # Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    FERNET_KEY: str = os.getenv("FERNET_KEY", "")  # empty = encryption disabled in dev

    # ── Rate Limiting ─────────────────────────────────────────────────────────
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_BURST:      int = 10   # additional burst allowance

    # ── Graph Settings ────────────────────────────────────────────────────────
    GRAPH_CACHE_TTL: int = 3600   # seconds

    # ── Neo4j (production graph) ──────────────────────────────────────────────
    USE_NEO4J:     bool = False
    NEO4J_URI:     str  = os.getenv("NEO4J_URI",     "bolt://localhost:7687")
    NEO4J_USER:    str  = os.getenv("NEO4J_USER",    "neo4j")
    NEO4J_PASSWORD:str  = os.getenv("NEO4J_PASSWORD","neo4j")

    # ── ML Service ────────────────────────────────────────────────────────────
    ML_SERVICE_URL: str = os.getenv("ML_SERVICE_URL", "http://localhost:8001")
    ML_TIMEOUT:     int = 30   # seconds

    # ── Circuit Breaker (pybreaker) ───────────────────────────────────────────
    CIRCUIT_BREAKER_FAIL_MAX:      int = 5    # open after N consecutive failures
    CIRCUIT_BREAKER_RESET_TIMEOUT: int = 60   # try recovery after N seconds

    # ── Zero-Day Anomaly Detector ─────────────────────────────────────────────
    ZERO_DAY_THRESHOLD: float = 0.60   # anomaly_score >= this → flag as zero-day

    # ── Celery ────────────────────────────────────────────────────────────────
    CELERY_BROKER_URL:     str = os.getenv("CELERY_BROKER_URL",     "redis://localhost:6379/1")
    CELERY_RESULT_BACKEND: str = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")

    # ── OpenTelemetry ─────────────────────────────────────────────────────────
    OTEL_EXPORTER_OTLP_ENDPOINT: str = os.getenv(
        "OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317"
    )
    OTEL_SERVICE_NAME: str = "threat-intel-api"

    # ── Scoring Weights (must sum to ≤ 1.0; anomaly is additive bonus) ────────
    MODEL_WEIGHT: float = 0.6
    GRAPH_WEIGHT: float = 0.4

    # ── Risk Thresholds ───────────────────────────────────────────────────────
    RISK_THRESHOLD_HIGH:   float = 0.70
    RISK_THRESHOLD_MEDIUM: float = 0.40

    # ── Model Drift Monitoring ────────────────────────────────────────────────
    DRIFT_WINDOW_DAYS:  int   = 7
    DRIFT_P_VALUE:      float = 0.05
    DRIFT_MIN_SAMPLES:  int   = 30

    # ── Data Retention ────────────────────────────────────────────────────────
    SCAN_RETENTION_DAYS: int = 90   # delete non-feedback scans older than this

    # ── HTML Sanitisation ─────────────────────────────────────────────────────
    # Tags allowed to pass through bleach when processing HTML input
    ALLOWED_HTML_TAGS: str = "a,b,i,u,em,strong,p,br"

    model_config = {
        "env_file": ".env",
        "case_sensitive": True,
        "extra": "ignore"
    }


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance (reloaded on restart)."""
    return Settings()


settings = get_settings()
