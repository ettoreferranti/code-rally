"""
Bot runtime system for CodeRally.

This package provides:
- Type definitions for bot API (types.py)
- Base bot class interface (base_bot.py)
- RestrictedPython sandbox (sandbox.py)
- Bot execution lifecycle (future: executor.py)
"""

from app.bot_runtime.types import (
    BotGameState,
    BotCarState,
    BotTrackState,
    BotRaycast,
    BotOpponent,
    BotRaceState,
    BotActions,
    CollisionEvent,
)
from app.bot_runtime.base_bot import BaseBot, GuardedBotBase
from app.bot_runtime.sandbox import (
    BotSandbox,
    SandboxSecurityError,
    SandboxTimeoutError,
    SandboxMemoryError,
)

__all__ = [
    # Type definitions
    "BotGameState",
    "BotCarState",
    "BotTrackState",
    "BotRaycast",
    "BotOpponent",
    "BotRaceState",
    "BotActions",
    "CollisionEvent",
    # Base classes
    "BaseBot",
    "GuardedBotBase",
    # Sandbox
    "BotSandbox",
    "SandboxSecurityError",
    "SandboxTimeoutError",
    "SandboxMemoryError",
]
