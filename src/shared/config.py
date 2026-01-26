"""
PubMed Scraper - Shared Configuration Module

Centralized settings management using Pydantic Settings.
Loads configuration from environment variables and .env files.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, MongoDsn, RedisDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """Core application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "pubmed-scraper"
    app_env: Literal["development", "staging", "production"] = "development"
    debug: bool = True
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    # API Server
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_reload: bool = True

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


class DatabaseSettings(BaseSettings):
    """MongoDB database settings."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    mongodb_url: MongoDsn = Field(default="mongodb://localhost:27017")
    mongodb_database: str = "pubmed_scraper"


class RedisSettings(BaseSettings):
    """Redis cache and queue settings."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    redis_url: RedisDsn = Field(default="redis://localhost:6379/0")
    celery_broker_url: RedisDsn = Field(default="redis://localhost:6379/1")
    celery_result_backend: RedisDsn = Field(default="redis://localhost:6379/2")


class S3Settings(BaseSettings):
    """S3/MinIO file storage settings."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    s3_endpoint_url: str = "http://localhost:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_bucket_name: str = "pubmed-papers"
    s3_region: str = "us-east-1"


class ExternalAPISettings(BaseSettings):
    """External API configuration for data sources."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # PubMed E-utilities
    pubmed_api_key: str | None = None
    ncbi_email: str = "your-email@example.com"
    pubmed_base_url: str = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

    # arXiv
    arxiv_base_url: str = "http://export.arxiv.org/api/query"

    # bioRxiv
    biorxiv_base_url: str = "https://api.biorxiv.org/details/biorxiv"


class RateLimitSettings(BaseSettings):
    """Rate limiting configuration per source."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    rate_limit_pubmed: int = 3  # requests per second
    rate_limit_arxiv: int = 1
    rate_limit_biorxiv: int = 2


class WorkerSettings(BaseSettings):
    """Celery worker configuration."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    celery_concurrency: int = 4
    max_retries: int = 3
    retry_delay: int = 5  # seconds


class Settings(BaseSettings):
    """Aggregated settings from all configuration classes."""

    app: AppSettings = Field(default_factory=AppSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    s3: S3Settings = Field(default_factory=S3Settings)
    external_api: ExternalAPISettings = Field(default_factory=ExternalAPISettings)
    rate_limit: RateLimitSettings = Field(default_factory=RateLimitSettings)
    worker: WorkerSettings = Field(default_factory=WorkerSettings)


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance (singleton pattern)."""
    return Settings()


# Convenience exports
settings = get_settings()
