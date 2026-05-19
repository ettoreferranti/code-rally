"""
Lobby system data structures for multiplayer race management.

This module defines the core data structures for managing race lobbies,
including lobby state, settings, members, and lobby lifecycle.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional
import time


class LobbyStatus(Enum):
    """Lobby state machine."""
    WAITING = "waiting"      # Lobby open, accepting players
    STARTING = "starting"    # Host triggered start, transitioning to race
    RACING = "racing"        # Race in progress
    FINISHED = "finished"    # Race complete, results shown
    DISBANDED = "disbanded"  # Lobby closed


@dataclass
class LobbySettings:
    """Configurable lobby settings."""
    track_difficulty: str = "medium"  # easy, medium, hard, extreme
    track_seed: Optional[int] = None  # Random if None
    max_players: int = 8
    finish_grace_period: int = 30  # Seconds after first finisher


@dataclass
class LobbyMember:
    """Individual member in a lobby.

    For bot members (driver_kind ∈ {python_bot, llm_bot}), ``bot_id`` is
    the DB row in the unified Bot table, and the kind-specific fields
    (bot_code/bot_class_name for python, llm_model_path/llm_system_prompt
    for llm) are denormalised at add-time so race-start doesn't have to
    re-query the DB.
    """
    player_id: str  # Unique player identifier
    username: Optional[str] = None  # Display name (if logged in)
    # Driver kind discriminator. "is_bot" stays True for both bot kinds for
    # back-compat; "driver_kind" carries the precise type the frontend roster
    # and the race-start dispatcher need.
    driver_kind: str = "human"  # "human" | "python_bot" | "llm_bot"
    is_bot: bool = False
    bot_id: Optional[int] = None  # Database bot ID (both python_bot and llm_bot)
    bot_code: Optional[str] = None  # python_bot only
    bot_class_name: Optional[str] = None  # python_bot only
    llm_model_path: Optional[str] = None  # llm_bot only
    llm_system_prompt: Optional[str] = None  # llm_bot only
    ready: bool = False  # Ready to start (future feature)
    connection_time: float = field(default_factory=time.time)


@dataclass
class Lobby:
    """Main lobby data structure.

    Two distinct identities matter here:
      - ``creator_player_id``: who originally made the lobby. NEVER changes.
        Used by the frontend to badge "YOUR LOBBY" rows on /lobbies.
      - ``host_player_id``: who can start the race right now. May transfer
        between members (e.g. when the original host leaves and other
        human members remain). Used for the start-race permission check.

    For freshly-created lobbies they're the same value; they diverge only
    after host transfer.
    """
    lobby_id: str  # UUID
    join_code: str  # Shareable code like "FAST-TIGER-42"
    name: str  # Display name
    host_player_id: str  # Current host — can start the race
    settings: LobbySettings
    members: Dict[str, LobbyMember]  # player_id -> LobbyMember
    creator_player_id: Optional[str] = None  # Original creator (stable identity)
    spectators: Dict[str, LobbyMember] = field(default_factory=dict)  # player_id -> LobbyMember
    status: LobbyStatus = LobbyStatus.WAITING
    created_at: float = field(default_factory=time.time)

    # Game session (only set when racing)
    game_session_id: Optional[str] = None

    # Track (generated when race starts)
    track: Optional['Track'] = None  # Forward reference to avoid circular import

    def get_member_count(self) -> int:
        """Get number of members in lobby (excludes spectators)."""
        return len(self.members)

    def get_spectator_count(self) -> int:
        """Get number of spectators in lobby."""
        return len(self.spectators)

    def is_host(self, player_id: str) -> bool:
        """Check if player is the lobby host."""
        return player_id == self.host_player_id

    def is_full(self) -> bool:
        """Check if lobby is at max capacity."""
        return len(self.members) >= self.settings.max_players

    def can_start_race(self) -> bool:
        """
        Check if race can start.

        Returns:
            True if race can start, False otherwise
        """
        return (
            self.status == LobbyStatus.WAITING and
            len(self.members) >= 1 and  # At least one player
            self.host_player_id in self.members  # Host still present
        )

    def transfer_host(self) -> None:
        """
        Transfer host to first remaining member.

        Called when current host leaves the lobby.
        """
        if not self.members:
            return

        # Transfer to first member
        self.host_player_id = next(iter(self.members.keys()))
