"""Core configuration module for Drift Detection Service."""

from functools import lru_cache
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    app_name: str = Field(default="Drift Detection Service", alias="APP_NAME")
    app_version: str = Field(default="1.0.0", alias="APP_VERSION")
    environment: str = Field(default="development", alias="ENVIRONMENT")
    debug: bool = Field(default=False, alias="DEBUG")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # API
    api_v1_prefix: str = Field(default="/api/v1", alias="API_V1_PREFIX")
    host: str = Field(default="0.0.0.0", alias="HOST")
    port: int = Field(default=8001, alias="PORT")

    # Database
    database_url: str = Field(..., alias="DATABASE_URL")
    db_pool_size: int = Field(default=10, alias="DB_POOL_SIZE")
    db_max_overflow: int = Field(default=20, alias="DB_MAX_OVERFLOW")
    db_pool_timeout: int = Field(default=30, alias="DB_POOL_TIMEOUT")
    db_echo: bool = Field(default=False, alias="DB_ECHO")

    # Drift Detection Parameters
    decay_half_life_days: int = Field(default=180, alias="DECAY_HALF_LIFE_DAYS")
    drift_signal_threshold: int = Field(default=3, alias="DRIFT_SIGNAL_THRESHOLD")
    drift_signal_window_days: int = Field(default=30, alias="DRIFT_SIGNAL_WINDOW_DAYS")
    semantic_gate_threshold: float = Field(default=0.55, alias="SEMANTIC_GATE_THRESHOLD")
    max_semantic_candidates: int = Field(default=5, alias="MAX_SEMANTIC_CANDIDATES")

    # Vector Embedding
    embedding_dimension: int = Field(default=3072, alias="EMBEDDING_DIMENSION")

    # CORS
    allowed_origins: List[str] = Field(
        default=["http://localhost:3000"], alias="ALLOWED_ORIGINS"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.
    
    Returns:
        Settings: Cached settings object
    """
    return Settings()
