"""
User model for bot ownership.

Simple username-only system for M3 (Bot Framework).
Full authentication with passwords will be added in M5 (Progression).
"""

from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime

from app.database import Base


class User(Base):
    """
    User model for bot ownership and identification.

    Attributes:
        id: Primary key
        username: Unique username (3-50 chars, alphanumeric + dash/underscore)
        created_at: User registration timestamp
        updated_at: Last modification timestamp
        bots: Relationship to user's bots (one-to-many)
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    bots = relationship("Bot", back_populates="owner", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}')>"
