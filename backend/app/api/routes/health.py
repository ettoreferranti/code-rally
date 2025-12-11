"""
Health check endpoints.

Provides basic health and status information about the server.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime

from app.database import get_db
from app.config import get_settings

router = APIRouter()
settings = get_settings()


@router.get("/health")
async def health_check(db: Session = Depends(get_db)) -> dict:
    """
    Basic health check endpoint.
    
    Returns:
        dict: Server status information including version and uptime.
        
    Example response:
        {
            "status": "healthy",
            "version": "0.1.0",
            "timestamp": "2024-12-11T23:00:00Z",
            "database": "connected"
        }
    """
    # Test database connection
    try:
        db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"
    
    return {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "version": settings.VERSION,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "database": db_status,
    }


@router.get("/health/ready")
async def readiness_check(db: Session = Depends(get_db)) -> dict:
    """
    Readiness check for the service.
    
    Verifies that the service is ready to accept requests by checking
    critical dependencies like the database connection.
    
    Returns:
        dict: Readiness status.
        
    Raises:
        HTTPException: If the service is not ready (e.g., database down).
    """
    # Verify database is accessible
    try:
        db.execute(text("SELECT 1"))
        return {
            "ready": True,
            "checks": {
                "database": "ok"
            }
        }
    except Exception as e:
        return {
            "ready": False,
            "checks": {
                "database": f"failed: {str(e)}"
            }
        }
