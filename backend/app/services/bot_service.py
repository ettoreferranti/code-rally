"""
Bot service layer for bot management operations.

Handles bot CRUD operations, code validation with RestrictedPython sandbox,
and duplicate name detection.
"""

import re
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models.bot import Bot
from app.bot_runtime.sandbox import BotSandbox, SandboxSecurityError, SandboxTimeoutError


# Maximum code size (100 KB)
MAX_CODE_SIZE = 100 * 1024


def extract_class_name(code: str) -> Optional[str]:
    """
    Extract the first class name from Python code.

    Args:
        code: Python source code

    Returns:
        Class name if found, None otherwise
    """
    # Simple regex to find class definitions
    class_pattern = re.compile(r'^\s*class\s+(\w+)', re.MULTILINE)
    match = class_pattern.search(code)
    return match.group(1) if match else None


def validate_bot_code(code: str) -> tuple[bool, Optional[str]]:
    """
    Validate bot code can compile and instantiate in sandbox.

    Args:
        code: Python source code to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not code or not code.strip():
        return False, "Bot code is required"

    if len(code) > MAX_CODE_SIZE:
        return False, f"Code size exceeds maximum of {MAX_CODE_SIZE} bytes"

    # Try to extract class name
    class_name = extract_class_name(code)
    if not class_name:
        return False, "No bot class found in code (must define a class inheriting from BaseBot)"

    # Try to compile and instantiate in sandbox
    try:
        sandbox = BotSandbox()
        sandbox.execute_bot_code(code, class_name)
        return True, None
    except SandboxSecurityError as e:
        return False, f"Security error: {str(e)}"
    except SandboxTimeoutError as e:
        return False, f"Timeout error: {str(e)}"
    except Exception as e:
        return False, f"Code error: {str(e)}"


def validate_bot_name(name: str) -> tuple[bool, Optional[str]]:
    """
    Validate bot name format.

    Args:
        name: Bot name to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not name or not name.strip():
        return False, "Bot name is required"

    name = name.strip()

    if len(name) < 1:
        return False, "Bot name must be at least 1 character"

    if len(name) > 100:
        return False, "Bot name must not exceed 100 characters"

    return True, None


def create_bot(db: Session, user_id: int, name: str, code: str) -> Bot:
    """
    Create a new bot.

    Args:
        db: Database session
        user_id: Owner user ID
        name: Bot display name
        code: Python source code

    Returns:
        Created Bot object

    Raises:
        ValueError: If validation fails or duplicate name exists
    """
    # Validate name
    is_valid, error_message = validate_bot_name(name)
    if not is_valid:
        raise ValueError(error_message)

    name = name.strip()

    # Validate code
    is_valid, error_message = validate_bot_code(code)
    if not is_valid:
        raise ValueError(error_message)

    # Check for duplicate name for this user
    existing_bot = db.query(Bot).filter(
        Bot.user_id == user_id,
        Bot.name == name
    ).first()

    if existing_bot:
        raise ValueError(f"Bot with name '{name}' already exists")

    # Create bot
    new_bot = Bot(
        name=name,
        code=code,
        user_id=user_id
    )

    db.add(new_bot)
    db.commit()
    db.refresh(new_bot)

    return new_bot


def update_bot(
    db: Session,
    bot_id: int,
    name: Optional[str] = None,
    code: Optional[str] = None
) -> Bot:
    """
    Update an existing bot.

    Args:
        db: Database session
        bot_id: Bot ID to update
        name: New bot name (optional)
        code: New Python source code (optional)

    Returns:
        Updated Bot object

    Raises:
        ValueError: If validation fails or bot not found
    """
    # Get bot
    bot = db.query(Bot).filter(Bot.id == bot_id).first()
    if not bot:
        raise ValueError("Bot not found")

    # Update name if provided
    if name is not None:
        is_valid, error_message = validate_bot_name(name)
        if not is_valid:
            raise ValueError(error_message)

        name = name.strip()

        # Check for duplicate name (excluding current bot)
        existing_bot = db.query(Bot).filter(
            Bot.user_id == bot.user_id,
            Bot.name == name,
            Bot.id != bot_id
        ).first()

        if existing_bot:
            raise ValueError(f"Bot with name '{name}' already exists")

        bot.name = name

    # Update code if provided
    if code is not None:
        is_valid, error_message = validate_bot_code(code)
        if not is_valid:
            raise ValueError(error_message)

        bot.code = code

    db.commit()
    db.refresh(bot)

    return bot


def delete_bot(db: Session, bot_id: int) -> bool:
    """
    Delete a bot.

    Args:
        db: Database session
        bot_id: Bot ID to delete

    Returns:
        True if deleted, False if not found
    """
    bot = db.query(Bot).filter(Bot.id == bot_id).first()
    if not bot:
        return False

    db.delete(bot)
    db.commit()

    return True


def get_bot_by_id(db: Session, bot_id: int) -> Optional[Bot]:
    """
    Get bot by ID.

    Args:
        db: Database session
        bot_id: Bot ID to lookup

    Returns:
        Bot object if found, None otherwise
    """
    return db.query(Bot).filter(Bot.id == bot_id).first()


def get_bots_by_user(db: Session, user_id: int) -> List[Bot]:
    """
    Get all bots for a user, ordered by most recently updated.

    Args:
        db: Database session
        user_id: User ID

    Returns:
        List of Bot objects
    """
    return db.query(Bot).filter(
        Bot.user_id == user_id
    ).order_by(Bot.updated_at.desc()).all()
