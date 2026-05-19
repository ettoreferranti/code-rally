"""
Database configuration and session management.

This module sets up SQLAlchemy with SQLite and provides
database session management for the application.
"""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session, declarative_base
from sqlalchemy.engine import Engine
import os
from pathlib import Path

from app.config import get_settings

settings = get_settings()

# Get the backend directory path (parent of app directory)
BACKEND_DIR = Path(__file__).parent.parent
DATA_DIR = BACKEND_DIR / "data"

# Ensure the data directory exists
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Database file path
DB_FILE = DATA_DIR / "coderally.db"
DATABASE_URL = f"sqlite:///{DB_FILE}"

# Create SQLAlchemy engine
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},  # Needed for SQLite
    echo=settings.database.ECHO_SQL,
)

# Enable foreign key constraints for SQLite
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    """Enable foreign key constraints on SQLite connections."""
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for all models (using SQLAlchemy 2.0 style)
Base = declarative_base()


def get_db() -> Session:
    """
    Dependency function to get database session.
    
    Yields:
        Session: Database session that will be automatically closed.
        
    Usage:
        @app.get("/users/{user_id}")
        async def read_user(user_id: int, db: Session = Depends(get_db)):
            return db.query(User).filter(User.id == user_id).first()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """
    Initialise the database.

    Creates all tables defined in the models if they don't exist, then
    runs idempotent ad-hoc migrations for columns SQLAlchemy
    `create_all` can't add to pre-existing tables.
    """
    # Import all models here so they are registered with Base
    from app.models.user import User
    from app.models.bot import Bot

    Base.metadata.create_all(bind=engine)
    _migrate_bots_table_for_llm_kind()
    print(f"Database initialised at {DB_FILE}")


def _migrate_bots_table_for_llm_kind() -> None:
    """Add the kind / model_path / system_prompt columns to existing
    `bots` tables that pre-date the Tinker / unified bot-library work.

    Idempotent: each `ALTER TABLE` only fires if the column is missing.
    """
    from sqlalchemy import text

    with engine.connect() as conn:
        existing_cols = {row[1] for row in conn.execute(text("PRAGMA table_info(bots)"))}
        if not existing_cols:
            return  # Fresh DB — create_all already produced the new schema.

        if "kind" not in existing_cols:
            conn.execute(text(
                "ALTER TABLE bots ADD COLUMN kind TEXT NOT NULL DEFAULT 'python'"
            ))
        if "model_path" not in existing_cols:
            conn.execute(text("ALTER TABLE bots ADD COLUMN model_path TEXT"))
        if "system_prompt" not in existing_cols:
            conn.execute(text("ALTER TABLE bots ADD COLUMN system_prompt TEXT"))
        conn.commit()
