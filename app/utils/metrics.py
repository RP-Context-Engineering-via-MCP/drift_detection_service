"""
Prometheus metrics for Drift Detection Service.

Tracks:
- Distributed lock metrics
- Event processing metrics
- Drift detection metrics
- API request metrics
"""

from prometheus_client import Counter, Histogram, Gauge, Summary
from typing import Optional
import time


# ============================================================================
# Distributed Lock Metrics
# ============================================================================

lock_acquisition_total = Counter(
    'drift_lock_acquisition_total',
    'Total number of lock acquisition attempts',
    ['lock_name', 'status']  # status: success, failed, timeout
)

lock_hold_duration_seconds = Histogram(
    'drift_lock_hold_duration_seconds',
    'Duration locks are held',
    ['lock_name'],
    buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0]
)

lock_contention_total = Counter(
    'drift_lock_contention_total',
    'Number of times lock acquisition was blocked',
    ['lock_name']
)


# ============================================================================
# Event Processing Metrics
# ============================================================================

events_processed_total = Counter(
    'drift_events_processed_total',
    'Total number of behavior events processed',
    ['status']  # status: success, duplicate, error
)

events_processing_duration_seconds = Histogram(
    'drift_events_processing_duration_seconds',
    'Time taken to process behavior events',
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0]
)

event_queue_size = Gauge(
    'drift_event_queue_size',
    'Current size of pending event queue'
)

idempotency_checks_total = Counter(
    'drift_idempotency_checks_total',
    'Total number of idempotency checks',
    ['result']  # result: new, duplicate
)


# ============================================================================
# Drift Detection Metrics
# ============================================================================

drift_scans_total = Counter(
    'drift_scans_total',
    'Total number of drift scans executed',
    ['status']  # status: success, failed, insufficient_data, cooldown
)

drift_scan_duration_seconds = Histogram(
    'drift_scan_duration_seconds',
    'Time taken to perform drift detection scan',
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0]
)

drift_events_detected_total = Counter(
    'drift_events_detected_total',
    'Total number of drift events detected',
    ['drift_type', 'severity']
)

drift_detector_execution_duration_seconds = Histogram(
    'drift_detector_execution_duration_seconds',
    'Time taken by individual detectors',
    ['detector_type'],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.0, 5.0]
)

drift_signals_aggregated_total = Counter(
    'drift_signals_aggregated_total',
    'Number of drift signals after aggregation',
    ['drift_type']
)

snapshot_build_duration_seconds = Histogram(
    'drift_snapshot_build_duration_seconds',
    'Time taken to build behavior snapshots',
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.0]
)

snapshot_behavior_count = Histogram(
    'drift_snapshot_behavior_count',
    'Number of behaviors in snapshot',
    buckets=[0, 5, 10, 20, 50, 100, 200, 500]
)


# ============================================================================
# Scheduler Metrics
# ============================================================================

scheduled_jobs_executed_total = Counter(
    'drift_scheduled_jobs_executed_total',
    'Total number of scheduled jobs executed',
    ['job_name', 'status']  # status: success, failed, skipped
)

scan_jobs_enqueued_total = Counter(
    'drift_scan_jobs_enqueued_total',
    'Total number of scan jobs enqueued',
    ['tier']  # tier: active, moderate
)

dead_letter_processed_total = Counter(
    'drift_dead_letter_processed_total',
    'Total number of dead letter messages processed'
)


# ============================================================================
# API Metrics
# ============================================================================

api_requests_total = Counter(
    'drift_api_requests_total',
    'Total number of API requests',
    ['method', 'endpoint', 'status_code']
)

api_request_duration_seconds = Histogram(
    'drift_api_request_duration_seconds',
    'API request duration',
    ['method', 'endpoint'],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
)

api_active_requests = Gauge(
    'drift_api_active_requests',
    'Number of currently active API requests'
)


# ============================================================================
# Database Metrics
# ============================================================================

db_query_duration_seconds = Histogram(
    'drift_db_query_duration_seconds',
    'Database query execution time',
    ['operation'],  # operation: select, insert, update, delete
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0]
)

db_connection_pool_size = Gauge(
    'drift_db_connection_pool_size',
    'Current database connection pool size',
    ['state']  # state: idle, active
)


# ============================================================================
# Redis Metrics
# ============================================================================

redis_operations_total = Counter(
    'drift_redis_operations_total',
    'Total number of Redis operations',
    ['operation', 'status']  # operation: get, set, sadd, sismember, etc.
)

redis_operation_duration_seconds = Histogram(
    'drift_redis_operation_duration_seconds',
    'Redis operation duration',
    ['operation'],
    buckets=[0.0001, 0.0005, 0.001, 0.005, 0.01, 0.05, 0.1]
)


# ============================================================================
# System Metrics
# ============================================================================

system_errors_total = Counter(
    'drift_system_errors_total',
    'Total number of system errors',
    ['error_type', 'component']
)

celery_task_execution_total = Counter(
    'drift_celery_task_execution_total',
    'Total number of Celery task executions',
    ['task_name', 'status']
)

celery_task_duration_seconds = Histogram(
    'drift_celery_task_duration_seconds',
    'Celery task execution duration',
    ['task_name'],
    buckets=[0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0, 120.0]
)


# ============================================================================
# Helper Context Managers
# ============================================================================

class timer:
    """Context manager for timing operations and recording to Prometheus histogram."""
    
    def __init__(self, histogram, *labels):
        """
        Initialize timer.
        
        Args:
            histogram: Prometheus histogram metric
            *labels: Label values for the histogram
        """
        self.histogram = histogram
        self.labels = labels
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time
        self.histogram.labels(*self.labels).observe(duration)


class active_requests_tracker:
    """Context manager for tracking active requests."""
    
    def __init__(self, gauge):
        """
        Initialize tracker.
        
        Args:
            gauge: Prometheus gauge metric
        """
        self.gauge = gauge
    
    def __enter__(self):
        self.gauge.inc()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.gauge.dec()


# ============================================================================
# Convenience Functions
# ============================================================================

def record_lock_acquisition(lock_name: str, success: bool, blocked: bool = False):
    """
    Record lock acquisition metrics.
    
    Args:
        lock_name: Name of the lock
        success: Whether lock was acquired
        blocked: Whether acquisition was blocked
    """
    status = 'success' if success else 'failed'
    lock_acquisition_total.labels(lock_name=lock_name, status=status).inc()
    
    if blocked:
        lock_contention_total.labels(lock_name=lock_name).inc()


def record_event_processing(status: str, duration: Optional[float] = None):
    """
    Record event processing metrics.
    
    Args:
        status: Processing status (success, duplicate, error)
        duration: Time taken to process (optional)
    """
    events_processed_total.labels(status=status).inc()
    
    if duration is not None:
        events_processing_duration_seconds.observe(duration)


def record_drift_detection(
    status: str,
    duration: Optional[float] = None,
    events_detected: Optional[list] = None
):
    """
    Record drift detection metrics.
    
    Args:
        status: Scan status (success, failed, insufficient_data, cooldown)
        duration: Time taken for detection
        events_detected: List of drift events detected
    """
    drift_scans_total.labels(status=status).inc()
    
    if duration is not None:
        drift_scan_duration_seconds.observe(duration)
    
    if events_detected:
        for event in events_detected:
            drift_events_detected_total.labels(
                drift_type=event.drift_type.value,
                severity=event.severity.value
            ).inc()


def record_api_request(method: str, endpoint: str, status_code: int, duration: float):
    """
    Record API request metrics.
    
    Args:
        method: HTTP method
        endpoint: API endpoint path
        status_code: HTTP status code
        duration: Request duration in seconds
    """
    api_requests_total.labels(
        method=method,
        endpoint=endpoint,
        status_code=str(status_code)
    ).inc()
    
    api_request_duration_seconds.labels(
        method=method,
        endpoint=endpoint
    ).observe(duration)
