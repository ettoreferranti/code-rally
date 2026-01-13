"""
REST API endpoints for lobby management.

Provides CRUD operations for lobbies:
- Create new lobby
- List available lobbies
- Get lobby details
- Update lobby settings (host only)
- Disband lobby (host only)
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
import logging

from app.core.lobby import LobbyStatus, LobbySettings
from app.core.lobby_manager import get_lobby_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/lobbies")


# ===== Pydantic Models =====

class CreateLobbyRequest(BaseModel):
    """Request to create a new lobby."""
    name: str = Field(..., min_length=1, max_length=50, description="Lobby display name")
    track_difficulty: str = Field(default="medium", description="Track difficulty (easy, medium, hard, extreme)")
    track_seed: Optional[int] = Field(default=None, description="Track seed for reproducible generation")
    max_players: int = Field(default=8, ge=1, le=8, description="Maximum players allowed")
    host_player_id: str = Field(..., description="Player ID of lobby creator")


class UpdateSettingsRequest(BaseModel):
    """Request to update lobby settings."""
    track_difficulty: Optional[str] = Field(default=None, description="Track difficulty")
    track_seed: Optional[int] = Field(default=None, description="Track seed")
    max_players: Optional[int] = Field(default=None, ge=1, le=8, description="Maximum players")


class LobbyMemberResponse(BaseModel):
    """Member information in a lobby."""
    player_id: str
    username: Optional[str] = None
    is_bot: bool = False
    bot_id: Optional[int] = None
    ready: bool = False


class LobbySettingsResponse(BaseModel):
    """Lobby settings response."""
    track_difficulty: str
    track_seed: Optional[int]
    max_players: int
    finish_grace_period: int


class LobbyResponse(BaseModel):
    """Full lobby details response."""
    lobby_id: str
    name: str
    host_player_id: str
    settings: LobbySettingsResponse
    members: List[LobbyMemberResponse]
    status: str
    created_at: float
    game_session_id: Optional[str] = None


class LobbyListItemResponse(BaseModel):
    """Lobby list item for browse view."""
    lobby_id: str
    name: str
    host_player_id: str
    member_count: int
    max_players: int
    status: str
    created_at: float


# ===== Helper Functions =====

def _lobby_to_response(lobby) -> LobbyResponse:
    """Convert Lobby dataclass to LobbyResponse."""
    return LobbyResponse(
        lobby_id=lobby.lobby_id,
        name=lobby.name,
        host_player_id=lobby.host_player_id,
        settings=LobbySettingsResponse(
            track_difficulty=lobby.settings.track_difficulty,
            track_seed=lobby.settings.track_seed,
            max_players=lobby.settings.max_players,
            finish_grace_period=lobby.settings.finish_grace_period
        ),
        members=[
            LobbyMemberResponse(
                player_id=member.player_id,
                username=member.username,
                is_bot=member.is_bot,
                bot_id=member.bot_id,
                ready=member.ready
            )
            for member in lobby.members.values()
        ],
        status=lobby.status.value,
        created_at=lobby.created_at,
        game_session_id=lobby.game_session_id
    )


def _lobby_to_list_item(lobby) -> LobbyListItemResponse:
    """Convert Lobby to list item response."""
    return LobbyListItemResponse(
        lobby_id=lobby.lobby_id,
        name=lobby.name,
        host_player_id=lobby.host_player_id,
        member_count=lobby.get_member_count(),
        max_players=lobby.settings.max_players,
        status=lobby.status.value,
        created_at=lobby.created_at
    )


# ===== REST Endpoints =====

@router.post("", response_model=LobbyResponse, status_code=201)
async def create_lobby(request: CreateLobbyRequest):
    """
    Create a new lobby.

    Args:
        request: Lobby creation parameters

    Returns:
        Created lobby details

    Raises:
        HTTPException: If creation fails
    """
    try:
        manager = get_lobby_manager()

        # Create lobby settings
        settings = LobbySettings(
            track_difficulty=request.track_difficulty,
            track_seed=request.track_seed,
            max_players=request.max_players
        )

        # Create lobby
        lobby = manager.create_lobby(
            name=request.name,
            host_player_id=request.host_player_id,
            settings=settings
        )

        logger.info(f"Created lobby {lobby.lobby_id} via REST API: '{lobby.name}'")
        return _lobby_to_response(lobby)

    except Exception as e:
        logger.error(f"Failed to create lobby: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create lobby: {str(e)}")


@router.get("", response_model=List[LobbyListItemResponse])
async def list_lobbies(
    status: Optional[str] = Query(default=None, description="Filter by status (waiting, starting, racing, finished)")
):
    """
    List all lobbies, optionally filtered by status.

    Args:
        status: Optional status filter

    Returns:
        List of lobbies sorted by creation time (newest first)
    """
    try:
        manager = get_lobby_manager()

        # Parse status filter
        status_filter = None
        if status:
            try:
                status_filter = LobbyStatus(status)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid status: {status}. Must be one of: waiting, starting, racing, finished, disbanded"
                )

        lobbies = manager.list_lobbies(status_filter=status_filter)

        return [_lobby_to_list_item(lobby) for lobby in lobbies]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list lobbies: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to list lobbies: {str(e)}")


@router.get("/{lobby_id}", response_model=LobbyResponse)
async def get_lobby(lobby_id: str):
    """
    Get full lobby details.

    Args:
        lobby_id: Lobby identifier

    Returns:
        Full lobby details

    Raises:
        HTTPException: If lobby not found
    """
    manager = get_lobby_manager()
    lobby = manager.get_lobby(lobby_id)

    if not lobby:
        raise HTTPException(status_code=404, detail=f"Lobby {lobby_id} not found")

    return _lobby_to_response(lobby)


@router.put("/{lobby_id}/settings", response_model=LobbyResponse)
async def update_lobby_settings(
    lobby_id: str,
    request: UpdateSettingsRequest,
    player_id: str = Query(..., description="Player ID attempting update (must be host)")
):
    """
    Update lobby settings (host only).

    Args:
        lobby_id: Lobby identifier
        request: Settings to update
        player_id: Player ID (must be host)

    Returns:
        Updated lobby details

    Raises:
        HTTPException: If lobby not found, not host, or update fails
    """
    manager = get_lobby_manager()
    lobby = manager.get_lobby(lobby_id)

    if not lobby:
        raise HTTPException(status_code=404, detail=f"Lobby {lobby_id} not found")

    # Build new settings (only update provided fields)
    new_settings = LobbySettings(
        track_difficulty=request.track_difficulty or lobby.settings.track_difficulty,
        track_seed=request.track_seed if request.track_seed is not None else lobby.settings.track_seed,
        max_players=request.max_players or lobby.settings.max_players,
        finish_grace_period=lobby.settings.finish_grace_period
    )

    success = manager.update_settings(lobby_id, player_id, new_settings)

    if not success:
        # Check why it failed
        if not lobby.is_host(player_id):
            raise HTTPException(status_code=403, detail="Only the host can update settings")
        elif lobby.status != LobbyStatus.WAITING:
            raise HTTPException(status_code=400, detail=f"Cannot update settings in status {lobby.status.value}")
        else:
            raise HTTPException(status_code=500, detail="Failed to update settings")

    # Return updated lobby
    updated_lobby = manager.get_lobby(lobby_id)
    return _lobby_to_response(updated_lobby)


@router.delete("/{lobby_id}", status_code=204)
async def disband_lobby(
    lobby_id: str,
    player_id: str = Query(..., description="Player ID attempting disband (must be host)")
):
    """
    Disband lobby (host only).

    Args:
        lobby_id: Lobby identifier
        player_id: Player ID (must be host)

    Raises:
        HTTPException: If lobby not found, not host, or disband fails
    """
    manager = get_lobby_manager()
    lobby = manager.get_lobby(lobby_id)

    if not lobby:
        raise HTTPException(status_code=404, detail=f"Lobby {lobby_id} not found")

    success = manager.disband_lobby(lobby_id, player_id)

    if not success:
        if not lobby.is_host(player_id):
            raise HTTPException(status_code=403, detail="Only the host can disband the lobby")
        else:
            raise HTTPException(status_code=500, detail="Failed to disband lobby")

    # 204 No Content - no response body
    return None
