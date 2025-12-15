"""
CodeRally Server Configuration

This file contains all server-side configurable settings.
Modify these values to tune the game behaviour.
"""

from dataclasses import dataclass
from typing import Optional
import os


@dataclass
class ServerConfig:
    """Server networking configuration."""
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    MAX_CONCURRENT_PLAYERS: int = 8
    WEBSOCKET_PING_INTERVAL: float = 30.0  # seconds


@dataclass
class GameConfig:
    """Core game settings."""
    TICK_RATE: int = 60  # Physics ticks per second
    BOT_TICK_RATE: int = 20  # Bot execution rate (Hz)
    MIN_CARS: int = 1
    MAX_CARS: int = 8
    COUNTDOWN_SECONDS: int = 3

    # Stage generation (point-to-point rally stages)
    STAGE_MIN_LENGTH: int = 1000  # units
    STAGE_MAX_LENGTH: int = 3000  # units
    STAGE_WIDTH: int = 160  # units (doubled for multi-car racing)
    CHECKPOINT_SPACING: int = 200  # Approximate distance between checkpoints
    FINISH_GRACE_PERIOD: int = 30  # Seconds after first finisher before DNF

    # Containment boundaries (outer walls that cars collide with)
    CONTAINMENT_OFFSET: float = 350.0  # Constant distance from track edge to wall (in units)
    CONTAINMENT_DISTANCE: float = 1.0  # Fixed distance from track edge (multiplier of track width) - for testing
    CONTAINMENT_MIN_DISTANCE: float = 0.5  # Minimum distance from track edge (multiplier of track width)
    CONTAINMENT_MAX_DISTANCE: float = 2.0  # Maximum distance from track edge (multiplier of track width)
    CONTAINMENT_SMOOTHING: float = 0.7  # Smoothing factor for transitions between segments (0-1, higher = smoother)
    BOTTLENECK_PROBABILITY: float = 0.0  # Chance of creating a tight bottleneck per section (disabled for now)
    BOTTLENECK_DISTANCE: float = 0.3  # Containment distance multiplier for bottlenecks (tight squeeze, min from track edge)

    # Obstacles (rocks, trees, buildings in off-road areas)
    OBSTACLE_DENSITY: float = 0.15  # Average obstacles per 1000 square units of off-road area
    OBSTACLE_MIN_RADIUS: float = 5.0  # Minimum obstacle size
    OBSTACLE_MAX_RADIUS: float = 20.0  # Maximum obstacle size
    OBSTACLE_MIN_DISTANCE_FROM_TRACK: float = 120.0  # Minimum distance from track centerline (must be > half track width)
    OBSTACLE_TYPES: tuple = ('rock', 'tree', 'building')  # Available obstacle types

    # Surface distribution (probabilities)
    SURFACE_ASPHALT_WEIGHT: float = 0.5
    SURFACE_GRAVEL_WEIGHT: float = 0.2
    SURFACE_WET_WEIGHT: float = 0.2
    SURFACE_ICE_WEIGHT: float = 0.1


@dataclass
class PhysicsConfig:
    """Physics simulation parameters."""
    # Movement
    MAX_SPEED: float = 150.0  # units/second (base, before upgrades)
    ACCELERATION: float = 80.0  # units/second^2
    BRAKE_FORCE: float = 120.0  # units/second^2
    DRAG_COEFFICIENT: float = 0.02
    
    # Turning
    TURN_RATE: float = 3.0  # radians/second
    MIN_TURN_SPEED: float = 5.0  # Minimum speed to turn effectively
    
    # Grip and drift
    GRIP_ASPHALT: float = 1.0
    GRIP_WET: float = 0.7
    GRIP_GRAVEL: float = 0.5
    GRIP_ICE: float = 0.25
    DRIFT_THRESHOLD: float = 0.6  # Grip ratio to start drifting
    DRIFT_RECOVERY_RATE: float = 2.0
    
    # Off-track penalty
    OFF_TRACK_SPEED_MULTIPLIER: float = 0.5
    OFF_TRACK_GRIP_MULTIPLIER: float = 0.3
    
    # Collisions (elastic)
    COLLISION_ELASTICITY: float = 0.7
    COLLISION_MIN_SPEED: float = 10.0  # Minimum impact speed


@dataclass
class BotConfig:
    """Bot sandbox configuration."""
    MEMORY_LIMIT_MB: int = 50
    EXECUTION_TIMEOUT_MS: int = 10
    MAX_CODE_SIZE_KB: int = 100
    MAX_STORED_VERSIONS: int = 10
    
    # Allowed imports
    ALLOWED_IMPORTS: tuple = ("math",)
    
    # State persistence
    MAX_STATE_SIZE_KB: int = 100


@dataclass
class CarConfig:
    """Car types and upgrade configuration."""
    # Base car stats (0-100 scale, modified by upgrades)
    CAR_TYPES: dict = None
    
    # Upgrade costs and limits
    UPGRADE_POINT_COST: int = 10  # Points per upgrade level
    MAX_UPGRADE_LEVEL: int = 10
    
    # Nitro defaults
    DEFAULT_NITRO_CHARGES: int = 2
    DEFAULT_NITRO_DURATION_TICKS: int = 120  # 2 seconds at 60 Hz
    NITRO_SPEED_MULTIPLIER: float = 1.5
    
    def __post_init__(self):
        if self.CAR_TYPES is None:
            self.CAR_TYPES = {
                "speedster": {
                    "top_speed": 80,
                    "acceleration": 50,
                    "grip": 50,
                    "braking": 50,
                    "handling": 60,
                    "weight": 30,
                },
                "tank": {
                    "top_speed": 50,
                    "acceleration": 40,
                    "grip": 70,
                    "braking": 70,
                    "handling": 40,
                    "weight": 90,
                },
                "balanced": {
                    "top_speed": 60,
                    "acceleration": 60,
                    "grip": 60,
                    "braking": 60,
                    "handling": 60,
                    "weight": 60,
                },
            }


@dataclass
class RaceConfig:
    """Race and progression settings."""
    # Points awarded by position
    POINTS_BY_POSITION: tuple = (25, 18, 15, 12, 10, 8, 6, 4)
    
    # Unlockables
    STARTING_CAR_TYPE: str = "balanced"
    CAR_UNLOCK_COSTS: dict = None
    
    def __post_init__(self):
        if self.CAR_UNLOCK_COSTS is None:
            self.CAR_UNLOCK_COSTS = {
                "speedster": 100,  # Points needed to unlock
                "tank": 100,
            }


@dataclass
class DatabaseConfig:
    """Database configuration."""
    DATABASE_URL: str = "sqlite:///./coderally.db"
    ECHO_SQL: bool = False  # Log SQL queries


@dataclass
class Settings:
    """Main settings container."""
    server: ServerConfig = None
    game: GameConfig = None
    physics: PhysicsConfig = None
    bot: BotConfig = None
    car: CarConfig = None
    race: RaceConfig = None
    database: DatabaseConfig = None
    
    # Application info
    APP_NAME: str = "CodeRally"
    VERSION: str = "0.1.0"
    DEBUG: bool = True
    
    def __post_init__(self):
        self.server = self.server or ServerConfig()
        self.game = self.game or GameConfig()
        self.physics = self.physics or PhysicsConfig()
        self.bot = self.bot or BotConfig()
        self.car = self.car or CarConfig()
        self.race = self.race or RaceConfig()
        self.database = self.database or DatabaseConfig()


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get the global settings instance."""
    return settings
