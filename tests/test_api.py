"""
API Tests

Test the REST API endpoints
"""

import pytest
from fastapi.testclient import TestClient
from api.main import app

# Create test client
client = TestClient(app)


# ============================================================================
# Health Check Tests
# ============================================================================

def test_root_endpoint():
    """Test root endpoint"""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Drift Detection API"
    assert data["version"] == "1.0.0"
    assert data["status"] == "running"


def test_health_check():
    """Test health check endpoint"""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "version" in data
    assert "database" in data
    assert "timestamp" in data


# ============================================================================
# Drift Detection Tests
# ============================================================================

def test_detect_drift_invalid_user():
    """Test drift detection with invalid user (no data)"""
    response = client.post("/api/v1/detect/nonexistent_user")
    # Should return 404 or appropriate error
    assert response.status_code in [404, 400]


def test_detect_drift_with_force_param():
    """Test drift detection with force parameter"""
    response = client.post("/api/v1/detect/test_user?force=true")
    # Will fail if user doesn't exist, but tests parameter handling
    assert response.status_code in [200, 404, 400]


# ============================================================================
# Get Events Tests
# ============================================================================

def test_get_drift_events():
    """Test getting drift events"""
    response = client.get("/api/v1/events/test_user")
    assert response.status_code == 200
    data = response.json()
    assert "user_id" in data
    assert "events" in data
    assert "total" in data
    assert "limit" in data
    assert "offset" in data
    assert data["user_id"] == "test_user"


def test_get_drift_events_with_filters():
    """Test getting drift events with filters"""
    response = client.get(
        "/api/v1/events/test_user"
        "?drift_type=TOPIC_EMERGENCE"
        "&severity=STRONG_DRIFT"
        "&limit=10"
        "&offset=0"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["limit"] == 10
    assert data["offset"] == 0


def test_get_drift_events_invalid_limit():
    """Test getting drift events with invalid limit"""
    response = client.get("/api/v1/events/test_user?limit=1000")
    # Should return validation error (max 500)
    assert response.status_code == 422


# ============================================================================
# Single Event Tests
# ============================================================================

def test_get_single_drift_event_not_found():
    """Test getting non-existent drift event"""
    response = client.get("/api/v1/events/test_user/nonexistent_event")
    assert response.status_code == 404


# ============================================================================
# Acknowledge Tests
# ============================================================================

def test_acknowledge_drift_event_not_found():
    """Test acknowledging non-existent drift event"""
    response = client.post(
        "/api/v1/events/test_user/nonexistent_event/acknowledge"
    )
    assert response.status_code == 404


# ============================================================================
# OpenAPI Schema Tests
# ============================================================================

def test_openapi_schema():
    """Test that OpenAPI schema is accessible"""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert schema["info"]["title"] == "Drift Detection API"
    assert schema["info"]["version"] == "1.0.0"


def test_swagger_ui():
    """Test that Swagger UI is accessible"""
    response = client.get("/docs")
    assert response.status_code == 200


def test_redoc():
    """Test that ReDoc is accessible"""
    response = client.get("/redoc")
    assert response.status_code == 200


# ============================================================================
# Error Handling Tests
# ============================================================================

def test_invalid_endpoint():
    """Test accessing invalid endpoint"""
    response = client.get("/api/v1/invalid_endpoint")
    assert response.status_code == 404


def test_invalid_method():
    """Test using wrong HTTP method"""
    response = client.get("/api/v1/detect/test_user")  # Should be POST
    assert response.status_code == 405  # Method Not Allowed
