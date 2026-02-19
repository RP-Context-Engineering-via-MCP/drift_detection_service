"""
Main FastAPI Application

REST API for Drift Detection Service
"""

import logging
from contextlib import asynccontextmanager
from urllib.parse import urlparse

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError

from api.routes import router
from api.dependencies import close_db_pool
from api.errors import (
    DriftDetectionError,
    drift_detection_error_handler,
    validation_error_handler,
    generic_error_handler
)
from app.config import get_settings
from app.scheduler import build_scheduler

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================================
# Lifespan Events
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events
    """
    # Startup
    logger.info("Starting Drift Detection API...")
    settings = get_settings()
    
    # Parse database URL for logging
    try:
        parsed_db = urlparse(settings.database_url)
        db_info = f"{parsed_db.hostname or 'localhost'}:{parsed_db.port or 5432}"
        if parsed_db.path:
            db_info += parsed_db.path
    except:
        db_info = "configured"
    
    logger.info(f"Database: {db_info}")
    
    # Start APScheduler
    scheduler = build_scheduler()
    scheduler.start()
    logger.info("APScheduler started with periodic jobs")
    
    logger.info("API is ready to accept requests")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Drift Detection API...")
    
    # Stop scheduler
    scheduler.shutdown(wait=False)
    logger.info("APScheduler stopped")
    
    close_db_pool()
    logger.info("Database connections closed")


# ============================================================================
# Create FastAPI Application
# ============================================================================

app = FastAPI(
    title="Drift Detection API",
    description="""
    REST API for behavioral drift detection service.
    
    ## Features
    
    * **Drift Detection**: Run drift detection for users
    * **Event Retrieval**: Get historical drift events with filtering
    * **Acknowledgment**: Mark drift events as acknowledged
    * **Health Check**: Monitor API and database status
    
    ## Drift Types
    
    * **TOPIC_EMERGENCE**: New topics appearing in behavior
    * **TOPIC_ABANDONMENT**: Previously active topics becoming silent
    * **PREFERENCE_REVERSAL**: Polarity changes (positive ↔ negative)
    * **INTENSITY_SHIFT**: Changes in credibility/certainty
    * **CONTEXT_EXPANSION**: Specific context → general
    * **CONTEXT_CONTRACTION**: General context → specific
    
    ## Severity Levels
    
    * **STRONG_DRIFT**: Score ≥ 0.8 (requires immediate attention)
    * **MODERATE_DRIFT**: Score 0.6-0.8 (notable change)
    * **WEAK_DRIFT**: Score 0.4-0.6 (minor change)
    * **NO_DRIFT**: Score < 0.4 (noise/insignificant)
    """,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)


# ============================================================================
# Middleware
# ============================================================================

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Exception Handlers
# ============================================================================

app.add_exception_handler(DriftDetectionError, drift_detection_error_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)
app.add_exception_handler(Exception, generic_error_handler)


# ============================================================================
# Routes
# ============================================================================

# Include API routes
app.include_router(router, prefix="/api/v1", tags=["Drift Detection"])


# Root endpoint
@app.get("/", tags=["Root"])
async def root():
    """Root endpoint with API information"""
    return {
        "name": "Drift Detection API",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
        "health": "/api/v1/health"
    }


# ============================================================================
# Run Application
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    
    settings = get_settings()
    
    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # Disable in production
        log_level="info"
    )
