"""
Run Drift Detection API

Start the FastAPI development server
"""

import uvicorn
from urllib.parse import urlparse
from app.config import get_settings


def main():
    """Start the FastAPI server"""
    settings = get_settings()
    
    # Parse database URL for display
    try:
        parsed_db = urlparse(settings.database_url)
        db_host = parsed_db.hostname or "localhost"
        db_port = parsed_db.port or 5432
        db_name = parsed_db.path.lstrip('/') if parsed_db.path else "unknown"
    except:
        db_host = "configured"
        db_port = ""
        db_name = ""
    
    print(f"""
╔═══════════════════════════════════════════════════════════╗
║         Drift Detection API - Starting Server            ║
╚═══════════════════════════════════════════════════════════╝

📊 API Information:
   • Host: 0.0.0.0
   • Port: 8000
   • Docs: http://localhost:8000/docs
   • ReDoc: http://localhost:8000/redoc

🗄️  Database:
   • Host: {db_host}
   • Port: {db_port}
   • Database: {db_name}

🔧 Configuration:
   • Min behaviors: {settings.min_behaviors_for_drift}
   • Min history: {settings.min_days_of_history} days
   • Cooldown: {settings.scan_cooldown_seconds}s
   • Drift threshold: {settings.drift_score_threshold}

Starting server...
""")
    
    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
        access_log=True
    )


if __name__ == "__main__":
    main()
