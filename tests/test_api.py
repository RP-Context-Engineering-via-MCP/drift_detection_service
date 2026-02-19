"""
Unit tests for API endpoints.

Tests for:
- Health check endpoint
- Drift detection endpoint
- Event retrieval endpoints
"""

import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from api.main import app
from api.models import DriftTypeAPI, DriftSeverityAPI
from api.dependencies import get_drift_detector


@pytest.fixture
def client():
    """Create a test client for the API."""
    return TestClient(app)


@pytest.fixture
def mock_drift_detector():
    """Create a mock drift detector using FastAPI dependency override."""
    detector = MagicMock()
    
    def override_get_drift_detector():
        return detector
    
    app.dependency_overrides[get_drift_detector] = override_get_drift_detector
    yield detector
    app.dependency_overrides.pop(get_drift_detector, None)


@pytest.fixture
def mock_db_pool():
    """Create a mock database pool."""
    with patch('api.dependencies.get_db_pool') as mock:
        pool = MagicMock()
        conn = MagicMock()
        cursor = MagicMock()
        
        pool.getconn.return_value = conn
        conn.cursor.return_value = cursor
        
        mock.return_value = pool
        yield pool


class TestHealthEndpoint:
    """Tests for health check endpoint."""
    
    def test_health_check_healthy(self, client):
        """Test health check returns healthy status."""
        with patch('api.routes.check_database_health', return_value=True):
            response = client.get("/api/v1/health")
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            assert data["database"] == "connected"
            assert "version" in data
            assert "timestamp" in data
    
    def test_health_check_unhealthy(self, client):
        """Test health check returns unhealthy status when DB is down."""
        with patch('api.routes.check_database_health', return_value=False):
            response = client.get("/api/v1/health")
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "unhealthy"
            assert data["database"] == "disconnected"


class TestDetectDriftEndpoint:
    """Tests for drift detection endpoint."""
    
    def test_detect_drift_success(self, client, mock_db_pool):
        """Test successful drift detection."""
        from app.models.drift import DriftEvent, DriftType, DriftSeverity
        
        # Mock behavior count check - user has 5 behaviors
        cursor = mock_db_pool.getconn().cursor()
        cursor.fetchone.return_value = (5,)
        
        # Mock drift detector at the route level
        mock_event = MagicMock()
        mock_event.drift_event_id = "drift_123"
        mock_event.user_id = "user_123"
        mock_event.drift_type = DriftType.TOPIC_EMERGENCE
        mock_event.drift_score = 0.8
        mock_event.severity = DriftSeverity.STRONG_DRIFT
        mock_event.affected_targets = ["python"]
        mock_event.evidence = {"test": True}
        mock_event.confidence = 0.9
        mock_event.reference_window_start = 1000000
        mock_event.reference_window_end = 1100000
        mock_event.current_window_start = 1100000
        mock_event.current_window_end = 1200000
        mock_event.detected_at = 1200000
        mock_event.acknowledged_at = None
        mock_event.behavior_ref_ids = []
        mock_event.conflict_ref_ids = []
        
        with patch('api.routes.DriftDetector') as mock_detector_class:
            mock_detector = MagicMock()
            mock_detector.detect_drift.return_value = [mock_event]
            mock_detector_class.return_value = mock_detector
            
            # Also need to patch the dependency
            with patch('api.dependencies.DriftDetector', mock_detector_class):
                response = client.post("/api/v1/detect/user_123")
        
                assert response.status_code == 200
                data = response.json()
                assert data["user_id"] == "user_123"
                assert data["total_events"] == 1
                assert len(data["detected_events"]) == 1
    
    def test_detect_drift_user_not_found(self, client, mock_db_pool):
        """Test detection fails when user has no data."""
        cursor = mock_db_pool.getconn().cursor()
        cursor.fetchone.return_value = (0,)  # User has 0 behaviors
        
        response = client.post("/api/v1/detect/nonexistent_user")
        
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["error"].lower()
    
    def test_detect_drift_no_events(self, client, mock_db_pool, mock_drift_detector):
        """Test detection returns empty when no drift detected."""
        cursor = mock_db_pool.getconn().cursor()
        cursor.fetchone.return_value = (5,)  # User has behaviors
        
        # Configure the mock drift detector to return empty list
        mock_drift_detector.detect_drift.return_value = []
        
        response = client.post("/api/v1/detect/user_123")
        
        assert response.status_code == 200
        data = response.json()
        assert data["total_events"] == 0
        assert "No drift detected" in data["message"]


class TestGetEventsEndpoint:
    """Tests for get drift events endpoint."""
    
    def test_get_events_success(self, client, mock_db_pool):
        """Test getting drift events for a user."""
        cursor = mock_db_pool.getconn().cursor()
        cursor.fetchall.return_value = [
            (
                "drift_001",
                "user_123",
                "TOPIC_EMERGENCE",
                0.85,
                "STRONG_DRIFT",
                ["python", "rust"],
                '{"test": true}',
                0.9,
                1000000,
                1100000,
                1100000,
                1200000,
                1200000,
                None,
                [],
                [],
            )
        ]
        cursor.fetchone.return_value = (1,)  # Total count
        
        response = client.get("/api/v1/events/user_123")
        
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == "user_123"
        assert data["total"] >= 0
    
    def test_get_events_with_filters(self, client, mock_db_pool):
        """Test getting events with type and severity filters."""
        cursor = mock_db_pool.getconn().cursor()
        cursor.fetchall.return_value = []
        cursor.fetchone.return_value = (0,)
        
        response = client.get(
            "/api/v1/events/user_123",
            params={
                "drift_type": "TOPIC_EMERGENCE",
                "severity": "STRONG_DRIFT",
                "limit": 10,
                "offset": 0,
            }
        )
        
        assert response.status_code == 200
    
    def test_get_events_pagination(self, client, mock_db_pool):
        """Test events endpoint pagination."""
        cursor = mock_db_pool.getconn().cursor()
        cursor.fetchall.return_value = []
        cursor.fetchone.return_value = (50,)  # 50 total events
        
        response = client.get(
            "/api/v1/events/user_123",
            params={"limit": 10, "offset": 20}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["limit"] == 10
        assert data["offset"] == 20


class TestAcknowledgeEndpoint:
    """Tests for acknowledge drift event endpoint."""
    
    def test_acknowledge_success(self, client, mock_db_pool):
        """Test successfully acknowledging a drift event."""
        cursor = mock_db_pool.getconn().cursor()
        # First call for getting the event, second for updating
        cursor.fetchone.side_effect = [
            (
                "drift_001",
                "user_123",
                "TOPIC_EMERGENCE",
                0.85,
                "STRONG_DRIFT",
                ["python"],
                '{}',
                0.9,
                1000000, 1100000, 1100000, 1200000,
                1200000,
                None,  # Not acknowledged
                [], []
            ),
            None  # Update returns nothing
        ]
        # Mock rowcount for update operation
        cursor.rowcount = 1
        
        # Correct path includes user_id
        response = client.post("/api/v1/events/user_123/drift_001/acknowledge")
        
        assert response.status_code == 200
        data = response.json()
        assert data["drift_event_id"] == "drift_001"
    
    def test_acknowledge_not_found(self, client, mock_db_pool):
        """Test acknowledging non-existent event."""
        cursor = mock_db_pool.getconn().cursor()
        cursor.fetchone.return_value = None  # Event not found
        
        # Correct path includes user_id
        response = client.post("/api/v1/events/user_123/nonexistent/acknowledge")
        
        assert response.status_code == 404


class TestAPIValidation:
    """Tests for API request validation."""
    
    def test_invalid_drift_type_filter(self, client):
        """Test that invalid drift type returns validation error."""
        response = client.get(
            "/api/v1/events/user_123",
            params={"drift_type": "INVALID_TYPE"}
        )
        
        assert response.status_code == 422  # Validation error
    
    def test_invalid_severity_filter(self, client):
        """Test that invalid severity returns validation error."""
        response = client.get(
            "/api/v1/events/user_123",
            params={"severity": "INVALID_SEVERITY"}
        )
        
        assert response.status_code == 422
    
    def test_negative_limit(self, client):
        """Test that negative limit returns validation error."""
        response = client.get(
            "/api/v1/events/user_123",
            params={"limit": -1}
        )
        
        assert response.status_code == 422
    
    def test_limit_exceeds_max(self, client):
        """Test that limit exceeding max returns validation error."""
        response = client.get(
            "/api/v1/events/user_123",
            params={"limit": 1000}  # Max is 500
        )
        
        assert response.status_code == 422
