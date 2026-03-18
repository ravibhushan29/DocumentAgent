"""Pydantic Settings — all env vars typed and validated (Section 21)."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings from environment. Fails at startup if required vars missing."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ── Application ──────────────────────────────────────────────────────
    APP_ENV: Literal["development", "staging", "production"] = Field(
        default="development",
        description="Environment name",
    )
    LOG_LEVEL: str = Field(default="INFO", description="Log level")
    ALLOWED_ORIGINS: str = Field(
        default="http://localhost:5173",
        description="Comma-separated CORS origins",
    )

    # ── Database ───────────────────────────────────────────────────────────
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://user:pass@localhost:5432/docdb",
        description="Async PostgreSQL URL",
    )
    PGBOUNCER_URL: str | None = Field(
        default=None,
        description="PgBouncer URL (optional, for connection pooling)",
    )

    # ── Redis ─────────────────────────────────────────────────────────────
    REDIS_URL: str = Field(default="redis://localhost:6379/0", description="Redis URL")
    REDIS_CACHE_DB: int = Field(default=2, description="DB index for RedisVL semantic cache")
    REDIS_CELERY_RESULT_DB: int = Field(default=1, description="DB index for Celery result backend")

    # ── Kafka ─────────────────────────────────────────────────────────────
    KAFKA_BOOTSTRAP_SERVERS: str = Field(default="localhost:9092", description="Kafka brokers")
    KAFKA_TOPIC_INGESTION: str = Field(default="doc.ingestion", description="Ingestion topic")
    KAFKA_TOPIC_RETRY: str = Field(default="doc.ingestion.retry", description="Retry topic")
    KAFKA_TOPIC_DLQ: str = Field(default="doc.ingestion.dlq", description="DLQ topic")
    KAFKA_TOPIC_EVENTS: str = Field(default="doc.events", description="Events topic")
    KAFKA_CONSUMER_GROUP: str = Field(default="ingestion-workers", description="Consumer group")
    KAFKA_SECURITY_PROTOCOL: Literal["PLAINTEXT", "SASL_SSL"] = Field(
        default="PLAINTEXT",
        description="Kafka security protocol",
    )

    # ── AWS ───────────────────────────────────────────────────────────────
    AWS_REGION: str = Field(default="us-east-1", description="AWS region")
    S3_BUCKET: str = Field(default="docagent-uploads-dev", description="S3 bucket for uploads")
    AWS_ACCESS_KEY_ID: str | None = Field(default=None, description="AWS access key (dev only)")
    AWS_SECRET_ACCESS_KEY: str | None = Field(default=None, description="AWS secret key (dev only)")

    # ── AI / Embeddings ───────────────────────────────────────────────────
    OPENAI_API_KEY: str = Field(default="", description="OpenAI API key")
    EMBEDDING_MODEL: str = Field(default="text-embedding-3-large", description="Embedding model")
    LLM_MODEL: str = Field(default="gpt-4o", description="LLM model for chat")
    EMBEDDING_BATCH_SIZE: int = Field(default=100, ge=1, le=500, description="Embedding batch size")

    # ── Auth ──────────────────────────────────────────────────────────────
    JWT_SECRET: str = Field(
        default="change-me-use-256-bit-random-string-in-prod",
        description="JWT signing secret",
    )
    JWT_EXPIRE_HOURS: int = Field(default=24, ge=1, le=168, description="JWT expiry in hours")

    # ── Observability ─────────────────────────────────────────────────────
    OTEL_EXPORTER_OTLP_ENDPOINT: str | None = Field(
        default=None,
        description="OTel collector gRPC endpoint",
    )
    OTEL_SERVICE_NAME: str = Field(default="docagent-api", description="Service name for traces")
    OTEL_TRACES_SAMPLER: str = Field(default="parentbased_traceidratio", description="Trace sampler")
    OTEL_TRACES_SAMPLER_ARG: str = Field(default="1.0", description="Sampler arg (e.g. 0.1 for 10%)")
    GLITCHTIP_DSN: str | None = Field(default=None, description="GlitchTip DSN for errors")
    PROMETHEUS_MULTIPROC_DIR: str = Field(
        default="/tmp/prometheus",
        description="Dir for Prometheus multi-process",
    )

    # ── Upload limits ─────────────────────────────────────────────────────
    MAX_FILE_BYTES: int = Field(
        default=524_288_000,
        description="Max upload size in bytes (500MB)",
    )
    ALLOWED_FILE_TYPES: str = Field(default="pdf,docx", description="Comma-separated allowed types")

    @property
    def is_development(self) -> bool:
        return self.APP_ENV == "development"

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance."""
    return Settings()
