"""
CodeRally FastAPI Application

Main entry point for the CodeRally game server.
Configures FastAPI with CORS, routes, and database.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.config import get_settings
from app.database import init_db
from app.api.routes import health, tracks

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events.
    
    Handles:
    - Database initialisation on startup
    - Cleanup on shutdown
    """
    # Startup
    print(f"Starting {settings.APP_NAME} v{settings.VERSION}")
    init_db()
    print(f"Server ready on {settings.server.HOST}:{settings.server.PORT}")
    
    yield
    
    # Shutdown
    print("Shutting down server...")


# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    description="A top-down 2D racing game with programmable AI bots",
    lifespan=lifespan,
    debug=settings.DEBUG,
)

# Configure CORS
# Allow specific origins for security in development
# In production, this should be even more restrictive
origins = [
    "http://localhost:5173",  # Vite default port
    "http://localhost:3000",  # Alternative React port
    "http://127.0.0.1:5173",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router, tags=["health"])
app.include_router(tracks.router, tags=["tracks"])


@app.get("/")
async def root() -> dict:
    """
    Root endpoint.
    
    Returns:
        dict: Welcome message and API information.
    """
    return {
        "message": f"Welcome to {settings.APP_NAME}",
        "version": settings.VERSION,
        "docs": "/docs",
        "health": "/health",
    }
