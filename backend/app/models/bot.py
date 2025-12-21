"""
Bot model for storing user-submitted racing bot code.

Each bot belongs to a user and contains Python code that inherits from BaseBot.
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime

from app.database import Base


class Bot(Base):
    """
    Bot model for persisting user-created racing bots.

    Attributes:
        id: Primary key
        name: Bot display name (1-100 chars)
        code: Python source code (validated with RestrictedPython)
        user_id: Foreign key to owner user
        created_at: Bot creation timestamp
        updated_at: Last modification timestamp
        owner: Relationship to User model
    """
    __tablename__ = "bots"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    code = Column(Text, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    owner = relationship("User", back_populates="bots")

    def __repr__(self):
        return f"<Bot(id={self.id}, name='{self.name}', user_id={self.user_id})>"
