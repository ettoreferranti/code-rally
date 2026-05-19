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

    A single table holds both kinds of bot, discriminated by ``kind``:
      - ``kind='python'``: ``code`` holds RestrictedPython source.
      - ``kind='llm'``: ``code`` is the empty string (kept NOT NULL for
        SQLite simplicity); ``model_path`` and ``system_prompt`` carry
        the LLM-specific config.

    Attributes:
        id: Primary key
        name: Bot display name (1-100 chars)
        kind: 'python' or 'llm'
        code: Python source code (Python bots) or '' (LLM bots)
        model_path: HuggingFace / local model path (LLM bots only)
        system_prompt: Strategist system prompt override (LLM bots only)
        user_id: Foreign key to owner user
        created_at: Bot creation timestamp
        updated_at: Last modification timestamp
        owner: Relationship to User model
    """
    __tablename__ = "bots"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    kind = Column(String(20), nullable=False, default="python", server_default="python")
    code = Column(Text, nullable=False, default="")
    model_path = Column(String(255), nullable=True)
    system_prompt = Column(Text, nullable=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    owner = relationship("User", back_populates="bots")

    def __repr__(self):
        return f"<Bot(id={self.id}, name='{self.name}', kind='{self.kind}', user_id={self.user_id})>"
