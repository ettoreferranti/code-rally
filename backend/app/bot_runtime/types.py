"""
Bot API type definitions for CodeRally.

This module defines the data structures that bots interact with:
- BotGameState: Complete sensor data available to bots
- BotActions: Commands bots can issue
- Event types: Collision events and callbacks

All bot-facing types are immutable (frozen dataclasses) to prevent
accidental state modification during bot execution.
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass(frozen=True)
class BotCarState:
    """
    Bot's own car state (sensor data).

    All properties are read-only to prevent bot code from modifying state.
    """
    position: Tuple[float, float]  # (x, y) position on track
    heading: float  # Direction facing (radians, 0 = right, π/2 = up)
    speed: float  # Current speed (units/second)
    velocity: Tuple[float, float]  # (vx, vy) velocity vector
    angular_velocity: float  # Rotation speed (radians/second)
    health: float  # Car health 0-100 (future feature)
    nitro_charges: int  # Remaining nitro uses
    nitro_active: bool  # Whether nitro is currently active
    current_surface: str  # Surface type: "asphalt", "gravel", "ice", "wet"
    off_track: bool  # Whether car is off the track


@dataclass(frozen=True)
class BotRaycast:
    """
    Raycast sensor result.

    Bots have 7 raycasts for obstacle detection in different directions.
    """
    distance: float  # Distance to obstacle (max 200 units)
    hit_type: Optional[str]  # "boundary", "car", "obstacle", or None


@dataclass(frozen=True)
class BotTrackState:
    """
    Track information available to bot.

    Includes checkpoints and upcoming track features.
    """
    checkpoints: List[Tuple[float, float]]  # List of checkpoint positions
    next_checkpoint: int  # Index of next checkpoint to reach
    distance_to_boundary_left: float  # Distance to left track edge
    distance_to_boundary_right: float  # Distance to right track edge
    upcoming_surface: str  # Surface type ahead
    upcoming_turn: str  # Next turn direction: "left", "right", "straight"
    turn_sharpness: float  # How sharp the upcoming turn is (0-1)


@dataclass(frozen=True)
class BotOpponent:
    """
    Opponent car data (fog of war applies - only nearby cars visible).
    """
    position: Tuple[float, float]  # (x, y) position
    velocity: Tuple[float, float]  # (vx, vy) velocity
    heading: float  # Direction facing (radians)
    distance: float  # Distance from bot's car
    relative_angle: float  # Angle relative to bot's heading


@dataclass(frozen=True)
class BotRaceState:
    """
    Race progress and standings.
    """
    current_checkpoint: int  # Index of next checkpoint to reach
    total_checkpoints: int  # Total checkpoints in stage
    position: int  # Current race position (1st, 2nd, etc.)
    total_cars: int  # Number of cars in race
    elapsed_time: float  # Stage time in seconds
    distance_to_finish: float  # Approximate distance to finish line


@dataclass(frozen=True)
class BotGameState:
    """
    Complete game state provided to bot's on_tick() method.

    Contains all sensor data the bot can "see".
    """
    car: BotCarState  # Bot's own car state
    track: BotTrackState  # Track information
    rays: List[BotRaycast]  # 7 vision raycasts
    opponents: List[BotOpponent]  # Visible opponent cars
    race: BotRaceState  # Race progress


@dataclass
class BotActions:
    """
    Actions that bot can perform.

    Returned by bot's on_tick() method to control the car.
    """
    accelerate: bool = False  # Apply forward thrust
    brake: bool = False  # Apply brakes (slow down)
    turn_left: bool = False  # Rotate counter-clockwise
    turn_right: bool = False  # Rotate clockwise
    use_nitro: bool = False  # Activate nitro boost (if available)

    def to_dict(self) -> dict:
        """Convert actions to dictionary format."""
        return {
            "accelerate": self.accelerate,
            "brake": self.brake,
            "turn_left": self.turn_left,
            "turn_right": self.turn_right,
            "use_nitro": self.use_nitro,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'BotActions':
        """Create BotActions from dictionary."""
        return cls(
            accelerate=data.get("accelerate", False),
            brake=data.get("brake", False),
            turn_left=data.get("turn_left", False),
            turn_right=data.get("turn_right", False),
            use_nitro=data.get("use_nitro", False),
        )


@dataclass(frozen=True)
class CollisionEvent:
    """
    Collision event data passed to bot's on_collision() callback.
    """
    other_type: str  # "car", "boundary", "obstacle"
    impact_speed: float  # How fast the collision was
    direction: float  # Angle of impact relative to bot's heading (radians)
    other_id: Optional[str]  # ID of other car (if car collision)
