"""
Configuration API endpoints.

Provides access to server configuration for clients.
"""

from fastapi import APIRouter
from typing import Dict, Any

from app.config import get_settings

router = APIRouter(prefix="/config", tags=["config"])


@router.get("/physics")
async def get_physics_config() -> Dict[str, Any]:
    """
    Get physics configuration parameters.

    Returns all physics constants used by the game engine. This ensures
    the frontend can synchronize its physics simulation with the backend.

    Returns:
        dict: Physics configuration with all constants
    """
    settings = get_settings()
    physics = settings.physics

    return {
        # Movement
        "MAX_SPEED": physics.MAX_SPEED,
        "ACCELERATION": physics.ACCELERATION,
        "BRAKE_FORCE": physics.BRAKE_FORCE,
        "DRAG_COEFFICIENT": physics.DRAG_COEFFICIENT,

        # Turning
        "TURN_RATE": physics.TURN_RATE,
        "MIN_TURN_SPEED": physics.MIN_TURN_SPEED,
        "TURN_ACCELERATION": physics.TURN_ACCELERATION,

        # Throttle
        "THROTTLE_RESPONSE": physics.THROTTLE_RESPONSE,

        # Grip and drift
        "GRIP_ASPHALT": physics.GRIP_ASPHALT,
        "GRIP_WET": physics.GRIP_WET,
        "GRIP_GRAVEL": physics.GRIP_GRAVEL,
        "GRIP_ICE": physics.GRIP_ICE,
        "DRIFT_THRESHOLD": physics.DRIFT_THRESHOLD,
        "DRIFT_RECOVERY_RATE": physics.DRIFT_RECOVERY_RATE,

        # Off-track penalties
        "OFF_TRACK_SPEED_MULTIPLIER": physics.OFF_TRACK_SPEED_MULTIPLIER,
        "OFF_TRACK_GRIP_MULTIPLIER": physics.OFF_TRACK_GRIP_MULTIPLIER,

        # Collisions
        "COLLISION_ELASTICITY": physics.COLLISION_ELASTICITY,
        "COLLISION_MIN_SPEED": physics.COLLISION_MIN_SPEED,
        "CAR_RADIUS": physics.CAR_RADIUS,
    }


@router.get("/game")
async def get_game_config() -> Dict[str, Any]:
    """
    Get game configuration parameters.

    Returns:
        dict: Game configuration including tick rates, player limits, etc.
    """
    settings = get_settings()
    game = settings.game

    return {
        "TICK_RATE": game.TICK_RATE,
        "BOT_TICK_RATE": game.BOT_TICK_RATE,
        "MAX_CARS": game.MAX_CARS,
        "COUNTDOWN_SECONDS": game.COUNTDOWN_SECONDS,
        "STAGE_WIDTH": game.STAGE_WIDTH,
    }
