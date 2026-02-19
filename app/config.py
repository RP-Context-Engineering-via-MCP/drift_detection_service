"""
Configuration module for Drift Detection Service.
Centralizes all thresholds, window sizes, and database settings.
"""

from functools import lru_cache
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False
    )
    
    # ─── Application Settings ────────────────────────────────────────────
    app_name: str = "Drift Detection Service"
    app_version: str = "1.0.0"
    environment: str = "development"
    debug: bool = True
    log_level: str = "INFO"
    
    # ─── Database Settings ───────────────────────────────────────────────
    database_url: str
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_timeout: int = 30
    db_echo: bool = False
    
    # ─── Redis Settings ──────────────────────────────────────────────────
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL for message broker and cache"
    )
    redis_stream_behavior_events: str = Field(
        default="behavior.events",
        description="Redis stream name for behavior events"
    )
    redis_stream_drift_events: str = Field(
        default="drift.events",
        description="Redis stream name for drift events"
    )
    redis_consumer_group: str = Field(
        default="drift_detection_service",
        description="Consumer group name for behavior event processing"
    )
    redis_consumer_name: str = Field(
        default="detector_1",
        description="Consumer name within the consumer group"
    )
    redis_block_ms: int = Field(
        default=5000,
        description="Block time in milliseconds when reading from streams"
    )
    redis_max_events_per_read: int = Field(
        default=10,
        description="Maximum events to read per stream read operation"
    )
    
    # ─── Celery Settings ─────────────────────────────────────────────────
    celery_broker_url: str = Field(
        default="redis://localhost:6379/1",
        description="Celery broker URL (Redis)"
    )
    celery_result_backend: str = Field(
        default="redis://localhost:6379/2",
        description="Celery result backend URL (Redis)"
    )
    celery_task_serializer: str = Field(
        default="json",
        description="Serialization format for task messages"
    )
    celery_result_serializer: str = Field(
        default="json",
        description="Serialization format for task results"
    )
    celery_accept_content: list = Field(
        default=["json"],
        description="Accepted content types for tasks"
    )
    celery_task_track_started: bool = Field(
        default=True,
        description="Track task execution start time"
    )
    celery_task_time_limit: int = Field(
        default=300,
        description="Hard time limit for tasks in seconds (5 minutes)"
    )
    celery_task_soft_time_limit: int = Field(
        default=240,
        description="Soft time limit for tasks in seconds (4 minutes)"
    )
    celery_worker_prefetch_multiplier: int = Field(
        default=1,
        description="Number of tasks a worker can prefetch at once"
    )
    celery_worker_max_tasks_per_child: int = Field(
        default=100,
        description="Maximum tasks a worker child process can execute before restart"
    )
    
    # ─── Scheduler Settings ──────────────────────────────────────────────
    active_user_scan_interval_hours: int = Field(
        default=24,
        description="Interval in hours for scanning active users"
    )
    moderate_user_scan_interval_hours: int = Field(
        default=72,
        description="Interval in hours for scanning moderate users (every 3 days)"
    )
    active_user_days_threshold: int = Field(
        default=7,
        description="Users active within this many days are considered 'active'"
    )
    moderate_user_days_threshold: int = Field(
        default=30,
        description="Users active within this many days are considered 'moderate'"
    )
    dead_letter_check_interval_minutes: int = Field(
        default=10,
        description="Interval in minutes for checking dead letter queue"
    )
    dead_letter_idle_threshold_ms: int = Field(
        default=300_000,
        description="Messages idle for this many milliseconds (5 min) are considered dead"
    )
    dead_letter_max_delivery_attempts: int = Field(
        default=3,
        description="Maximum delivery attempts before moving to dead letter queue"
    )
    
    # ─── Drift Detection Thresholds ──────────────────────────────────────
    
    # Minimum data requirements for drift detection
    min_behaviors_for_drift: int = Field(
        default=5,
        description="Minimum number of active behaviors required to run drift detection"
    )
    min_days_of_history: int = Field(
        default=14,
        description="Minimum days of behavior history required"
    )
    
    # Cooldown between drift scans for the same user
    scan_cooldown_seconds: int = Field(
        default=3600,  # 1 hour
        description="Minimum seconds between drift scans for the same user"
    )
    
    # Drift score threshold for creating events
    drift_score_threshold: float = Field(
        default=0.6,
        ge=0.0,
        le=1.0,
        description="Minimum drift score to create a drift event (0.0-1.0)"
    )
    
    # ─── Time Window Configuration ───────────────────────────────────────
    
    current_window_days: int = Field(
        default=30,
        description="Size of current behavior window in days"
    )
    reference_window_start_days: int = Field(
        default=60,
        description="How far back the reference window starts (days ago)"
    )
    reference_window_end_days: int = Field(
        default=30,
        description="How far back the reference window ends (days ago)"
    )
    
    # ─── Detector-Specific Thresholds ────────────────────────────────────
    
    # Topic Abandonment
    abandonment_silence_days: int = Field(
        default=30,
        description="Days of no activity to consider a topic abandoned"
    )
    min_reinforcement_for_abandonment: int = Field(
        default=2,
        description="Minimum historical reinforcement count to flag abandonment"
    )
    
    # Intensity Shift
    intensity_delta_threshold: float = Field(
        default=0.25,
        ge=0.0,
        le=1.0,
        description="Minimum credibility change to detect intensity shift"
    )
    
    # Topic Emergence
    emergence_min_reinforcement: int = Field(
        default=2,
        description="Minimum mentions to consider a topic as emerging"
    )
    emergence_cluster_min_size: int = Field(
        default=3,
        description="Minimum cluster size for domain emergence detection"
    )
    
    # ─── Embedding & Clustering Settings ─────────────────────────────────
    
    embedding_model: str = Field(
        default="all-MiniLM-L6-v2",
        description="Sentence transformer model for topic embeddings"
    )
    embedding_dimension: int = Field(
        default=384,
        description="Dimension of embedding vectors"
    )
    embedding_cluster_eps: float = Field(
        default=0.4,
        ge=0.0,
        le=1.0,
        description="DBSCAN epsilon parameter for clustering"
    )
    embedding_cluster_min_samples: int = Field(
        default=2,
        description="DBSCAN min_samples parameter"
    )
    
    # ─── Scoring Weights ─────────────────────────────────────────────────
    
    recency_weight_days: int = Field(
        default=30,
        description="Days for recency weight calculation in emergence detection"
    )
    
    # ─── Helper Methods ──────────────────────────────────────────────────
    
    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment.lower() == "production"
    
    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment.lower() == "development"
    
    def get_reference_window(self) -> tuple[int, int]:
        """
        Get reference window boundaries in days ago.
        Returns: (start_days_ago, end_days_ago)
        """
        return (self.reference_window_start_days, self.reference_window_end_days)
    
    def get_current_window_days(self) -> int:
        """Get current window size in days."""
        return self.current_window_days


@lru_cache
def get_settings() -> Settings:
    """
    Get cached application settings.
    
    Uses LRU cache to ensure settings are loaded only once.
    Call this function to access configuration throughout the application.
    
    Returns:
        Settings: Application configuration object
    """
    return Settings()


# Convenience function for quick access to settings
def get_config() -> Settings:
    """Alias for get_settings()."""
    return get_settings()
