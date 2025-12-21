"""
User API endpoints for username-based user management.

Provides simple username registration (no password) for M3.
Full authentication will be added in M5.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import List
from datetime import datetime

from app.database import get_db
from app.services import user_service


router = APIRouter(prefix="/users", tags=["users"])


# Request/Response models
class RegisterUserRequest(BaseModel):
    """Request model for user registration."""
    username: str = Field(..., min_length=3, max_length=50, description="Username (3-50 characters)")


class UserResponse(BaseModel):
    """Response model for user data."""
    id: int
    username: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


@router.get("", response_model=List[UserResponse])
async def list_users(db: Session = Depends(get_db)):
    """
    List all users.

    Args:
        db: Database session

    Returns:
        List of all users
    """
    users = user_service.get_all_users(db)
    return users


@router.post("/register", response_model=UserResponse, status_code=201)
async def register_user(
    request: RegisterUserRequest,
    db: Session = Depends(get_db)
):
    """
    Register or retrieve user by username (idempotent operation).

    If username already exists, returns the existing user.
    If username is new, creates a new user.

    Args:
        request: User registration request
        db: Database session

    Returns:
        User object (new or existing)

    Raises:
        400: Invalid username format
        500: Database error
    """
    try:
        user = user_service.get_or_create_user(db, request.username)
        return user
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/{username}", response_model=UserResponse)
async def get_user(
    username: str,
    db: Session = Depends(get_db)
):
    """
    Get user by username.

    Args:
        username: Username to lookup
        db: Database session

    Returns:
        User object

    Raises:
        404: User not found
    """
    user = user_service.get_user_by_username(db, username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return user


@router.delete("/{username}", status_code=204)
async def delete_user(
    username: str,
    db: Session = Depends(get_db)
):
    """
    Delete a user and all their bots.

    Args:
        username: Username to delete
        db: Database session

    Returns:
        No content (204)

    Raises:
        404: User not found
    """
    success = user_service.delete_user(db, username)
    if not success:
        raise HTTPException(status_code=404, detail="User not found")

    return None
