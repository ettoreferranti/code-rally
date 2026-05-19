"""
Bot API endpoints for CRUD operations on user bots.

Provides bot management with RestrictedPython validation for Python bots
and persistence of model_path + system_prompt for LLM bots.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List
from datetime import datetime

from app.database import get_db
from app.services import bot_service, user_service
from app.bot_runtime.templates import get_template_list, get_template_code


router = APIRouter(prefix="/bots", tags=["bots"])


# Request/Response models
_BOT_MODEL_CONFIG = ConfigDict(from_attributes=True, protected_namespaces=())


class CreateBotRequest(BaseModel):
    """Request model for creating either a Python or LLM bot.

    The `kind` discriminator selects which kind-specific fields apply:
      - 'python' (default): `code` is required.
      - 'llm': `model_path` and `system_prompt` are required.
    """
    model_config = ConfigDict(protected_namespaces=())

    name: str = Field(..., min_length=1, max_length=100, description="Bot display name")
    kind: str = Field("python", description="'python' or 'llm'")
    code: Optional[str] = Field(None, description="Python source code (required for kind='python')")
    model_path: Optional[str] = Field(None, description="Model path (required for kind='llm')")
    system_prompt: Optional[str] = Field(None, description="System prompt (required for kind='llm')")


class UpdateBotRequest(BaseModel):
    """Request model for updating a bot.

    Update fields that match the bot's `kind`. Kind itself is immutable
    after creation.
    """
    model_config = ConfigDict(protected_namespaces=())

    name: Optional[str] = Field(None, min_length=1, max_length=100, description="New bot name (optional)")
    code: Optional[str] = Field(None, min_length=1, description="New Python source code (Python bots only)")
    model_path: Optional[str] = Field(None, description="New model path (LLM bots only)")
    system_prompt: Optional[str] = Field(None, description="New system prompt (LLM bots only)")


class BotResponse(BaseModel):
    """Response model for bot data (full)."""
    model_config = _BOT_MODEL_CONFIG

    id: int
    name: str
    kind: str
    code: str
    model_path: Optional[str] = None
    system_prompt: Optional[str] = None
    user_id: int
    created_at: datetime
    updated_at: datetime


class BotListResponse(BaseModel):
    """Response model for bot listing (kind + model surfaced; code omitted)."""
    model_config = _BOT_MODEL_CONFIG

    id: int
    name: str
    kind: str
    model_path: Optional[str] = None
    user_id: int
    created_at: datetime
    updated_at: datetime


@router.get("/users/{username}/bots", response_model=List[BotListResponse])
async def list_user_bots(
    username: str,
    db: Session = Depends(get_db)
):
    """
    List all bots for a user, ordered by most recently updated.

    Args:
        username: Username to lookup
        db: Database session

    Returns:
        List of bot objects (without code for performance)

    Raises:
        404: User not found
    """
    # Check user exists
    user = user_service.get_user_by_username(db, username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    bots = bot_service.get_bots_by_user(db, user.id)
    return bots


# ====================================================================
# Template Endpoints
# ====================================================================


class TemplateInfo(BaseModel):
    """Template metadata."""
    id: str
    name: str
    difficulty: int
    description: str
    features: List[str]


class TemplateCodeResponse(BaseModel):
    """Template code response."""
    id: str
    name: str
    code: str


@router.get("/templates", response_model=List[TemplateInfo])
async def list_templates():
    """
    Get list of available bot templates.

    Returns:
        List of template metadata (without code for performance)
    """
    templates = get_template_list()
    return [
        TemplateInfo(
            id=t["id"],
            name=t["name"],
            difficulty=t["difficulty"],
            description=t["description"],
            features=t["features"]
        )
        for t in templates
    ]


@router.get("/templates/{template_id}", response_model=TemplateCodeResponse)
async def get_template(template_id: str):
    """
    Get source code for a specific template.

    Args:
        template_id: Template identifier (e.g., "simple_follower")

    Returns:
        Template code and metadata

    Raises:
        404: Template not found
    """
    try:
        code = get_template_code(template_id)

        # Get template metadata
        templates = get_template_list()
        template = next((t for t in templates if t["id"] == template_id), None)

        return TemplateCodeResponse(
            id=template_id,
            name=template["name"] if template else template_id,
            code=code
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{bot_id}", response_model=BotResponse)
async def get_bot(
    bot_id: int,
    db: Session = Depends(get_db)
):
    """
    Get a specific bot by ID (includes code).

    Args:
        bot_id: Bot ID to lookup
        db: Database session

    Returns:
        Bot object with code

    Raises:
        404: Bot not found
    """
    bot = bot_service.get_bot_by_id(db, bot_id)
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")

    return bot


@router.post("/users/{username}/bots", response_model=BotResponse, status_code=201)
async def create_bot(
    username: str,
    request: CreateBotRequest,
    db: Session = Depends(get_db)
):
    """
    Create a new bot for a user.

    Validates code with RestrictedPython sandbox before saving.
    Checks for duplicate bot names for the user.

    Args:
        username: Owner username
        request: Bot creation request
        db: Database session

    Returns:
        Created bot object

    Raises:
        404: User not found
        400: Invalid bot data (validation, duplicate name, sandbox error)
        500: Database error
    """
    # Check user exists
    user = user_service.get_user_by_username(db, username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    try:
        if request.kind == "python":
            if not request.code:
                raise HTTPException(status_code=400, detail="`code` is required for kind='python'")
            bot = bot_service.create_bot(db, user.id, request.name, request.code)
        elif request.kind == "llm":
            if not request.model_path or not request.system_prompt:
                raise HTTPException(
                    status_code=400,
                    detail="`model_path` and `system_prompt` are required for kind='llm'",
                )
            bot = bot_service.create_llm_bot(
                db, user.id, request.name, request.model_path, request.system_prompt
            )
        else:
            raise HTTPException(status_code=400, detail=f"Unknown bot kind: {request.kind!r}")
        return bot
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.put("/{bot_id}", response_model=BotResponse)
async def update_bot(
    bot_id: int,
    request: UpdateBotRequest,
    db: Session = Depends(get_db)
):
    """
    Update an existing bot.

    Can update name, code, or both. Validates code with RestrictedPython
    if code is being updated. Checks for duplicate names if name is updated.

    Args:
        bot_id: Bot ID to update
        request: Update request with optional name and/or code
        db: Database session

    Returns:
        Updated bot object

    Raises:
        400: Invalid update data (validation, duplicate name, sandbox error)
        404: Bot not found
        500: Database error
    """
    # Ensure at least one field is being updated
    if (
        request.name is None
        and request.code is None
        and request.model_path is None
        and request.system_prompt is None
    ):
        raise HTTPException(
            status_code=400,
            detail="Must provide at least one field to update",
        )

    try:
        bot = bot_service.update_bot(
            db,
            bot_id,
            name=request.name,
            code=request.code,
            model_path=request.model_path,
            system_prompt=request.system_prompt,
        )
        return bot
    except ValueError as e:
        # Check if it's a "not found" error
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.delete("/{bot_id}", status_code=204)
async def delete_bot(
    bot_id: int,
    db: Session = Depends(get_db)
):
    """
    Delete a bot.

    Args:
        bot_id: Bot ID to delete
        db: Database session

    Returns:
        No content (204)

    Raises:
        404: Bot not found
    """
    success = bot_service.delete_bot(db, bot_id)
    if not success:
        raise HTTPException(status_code=404, detail="Bot not found")

    return None
