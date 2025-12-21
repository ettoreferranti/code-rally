"""
User service layer for user management operations.

Handles user creation, retrieval, and username validation.
"""

import re
from typing import Optional, List
from sqlalchemy.orm import Session

from app.models.user import User


# Username validation regex: 3-50 characters, alphanumeric + dash/underscore
USERNAME_PATTERN = re.compile(r'^[a-zA-Z0-9_-]{3,50}$')


def validate_username(username: str) -> tuple[bool, Optional[str]]:
    """
    Validate username format.

    Args:
        username: Username to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not username:
        return False, "Username is required"

    username = username.strip()

    if len(username) < 3:
        return False, "Username must be at least 3 characters"

    if len(username) > 50:
        return False, "Username must not exceed 50 characters"

    if not USERNAME_PATTERN.match(username):
        return False, "Username can only contain letters, numbers, dashes, and underscores"

    return True, None


def get_or_create_user(db: Session, username: str) -> User:
    """
    Get existing user or create new user (idempotent operation).

    Args:
        db: Database session
        username: Username to register/retrieve

    Returns:
        User object (existing or newly created)

    Raises:
        ValueError: If username validation fails
    """
    # Validate username
    is_valid, error_message = validate_username(username)
    if not is_valid:
        raise ValueError(error_message)

    username = username.strip()

    # Check if user already exists
    existing_user = db.query(User).filter(User.username == username).first()
    if existing_user:
        return existing_user

    # Create new user
    new_user = User(username=username)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return new_user


def get_user_by_username(db: Session, username: str) -> Optional[User]:
    """
    Get user by username.

    Args:
        db: Database session
        username: Username to lookup

    Returns:
        User object if found, None otherwise
    """
    return db.query(User).filter(User.username == username).first()


def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    """
    Get user by ID.

    Args:
        db: Database session
        user_id: User ID to lookup

    Returns:
        User object if found, None otherwise
    """
    return db.query(User).filter(User.id == user_id).first()


def get_all_users(db: Session) -> List[User]:
    """
    Get all users, ordered by username.

    Args:
        db: Database session

    Returns:
        List of all User objects
    """
    return db.query(User).order_by(User.username).all()


def delete_user(db: Session, username: str) -> bool:
    """
    Delete a user by username.

    Cascades to delete all bots owned by this user.

    Args:
        db: Database session
        username: Username to delete

    Returns:
        True if deleted, False if not found
    """
    user = db.query(User).filter(User.username == username).first()
    if not user:
        return False

    db.delete(user)
    db.commit()

    return True
