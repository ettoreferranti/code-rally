"""
Lobby manager for multiplayer race lobbies.

This module manages all active lobbies (in-memory storage),
tracks lobby state transitions, and handles player membership.
"""

import asyncio
import time
import logging
from typing import Dict, List, Optional, Tuple
from uuid import uuid4

from app.core.lobby import Lobby, LobbyStatus, LobbySettings, LobbyMember
from app.core.track import TrackGenerator, Track
from app.core.join_code import generate_join_code

logger = logging.getLogger(__name__)


class LobbyManager:
    """
    Manages all active lobbies (in-memory storage).
    Tracks lobby state transitions and player membership.
    """

    def __init__(self):
        """Initialize lobby manager."""
        self._lobbies: Dict[str, Lobby] = {}
        self._join_codes: Dict[str, str] = {}  # join_code -> lobby_id mapping
        self._lock = asyncio.Lock()  # Thread-safe operations

    def create_lobby(
        self,
        name: str,
        host_player_id: str,
        settings: Optional[LobbySettings] = None
    ) -> Lobby:
        """
        Create new lobby and return it.

        Args:
            name: Display name for the lobby
            host_player_id: Player who created the lobby
            settings: Lobby settings (uses defaults if None)

        Returns:
            Newly created Lobby instance
        """
        lobby_id = str(uuid4())

        # Generate unique join code (retry if collision)
        max_attempts = 10
        join_code = None
        for _ in range(max_attempts):
            code = generate_join_code()
            if code not in self._join_codes:
                join_code = code
                break

        if not join_code:
            # Fallback to UUID suffix if can't generate unique code
            join_code = f"LOBBY-{lobby_id[:8].upper()}"

        lobby = Lobby(
            lobby_id=lobby_id,
            join_code=join_code,
            name=name,
            host_player_id=host_player_id,
            settings=settings or LobbySettings(),
            members={
                host_player_id: LobbyMember(
                    player_id=host_player_id,
                    ready=True  # Host auto-ready
                )
            }
        )
        self._lobbies[lobby_id] = lobby
        self._join_codes[join_code] = lobby_id
        logger.info(f"Created lobby {lobby_id} (code: {join_code}): '{name}' (host: {host_player_id})")
        return lobby

    def get_lobby(self, lobby_id: str) -> Optional[Lobby]:
        """
        Get lobby by ID.

        Args:
            lobby_id: Lobby identifier

        Returns:
            Lobby if found, None otherwise
        """
        return self._lobbies.get(lobby_id)

    def get_lobby_by_code(self, join_code: str) -> Optional[Lobby]:
        """
        Get lobby by join code.

        Args:
            join_code: Join code (e.g., "FAST-TIGER-42")

        Returns:
            Lobby if found, None otherwise
        """
        lobby_id = self._join_codes.get(join_code.upper())
        if lobby_id:
            return self._lobbies.get(lobby_id)
        return None

    def list_lobbies(self, status_filter: Optional[LobbyStatus] = None) -> List[Lobby]:
        """
        List all lobbies, optionally filtered by status.

        Args:
            status_filter: Only return lobbies with this status (None = all)

        Returns:
            List of lobbies sorted by creation time (newest first)
        """
        lobbies = list(self._lobbies.values())
        if status_filter:
            lobbies = [l for l in lobbies if l.status == status_filter]
        return sorted(lobbies, key=lambda l: l.created_at, reverse=True)

    def join_lobby(
        self,
        lobby_id: str,
        player_id: str,
        username: Optional[str] = None
    ) -> bool:
        """
        Add player to lobby.

        Args:
            lobby_id: Lobby to join
            player_id: Player identifier
            username: Optional display name

        Returns:
            True if successful, False otherwise
        """
        lobby = self._lobbies.get(lobby_id)
        if not lobby:
            logger.warning(f"Player {player_id} tried to join non-existent lobby {lobby_id}")
            return False

        if lobby.status != LobbyStatus.WAITING:
            logger.warning(f"Player {player_id} tried to join lobby {lobby_id} in status {lobby.status}")
            return False

        if lobby.is_full():
            logger.warning(f"Player {player_id} tried to join full lobby {lobby_id}")
            return False

        if player_id in lobby.members:
            logger.debug(f"Player {player_id} already in lobby {lobby_id}")
            return True  # Already joined

        lobby.members[player_id] = LobbyMember(
            player_id=player_id,
            username=username
        )
        logger.info(f"Player {player_id} joined lobby {lobby_id} ({lobby.get_member_count()}/{lobby.settings.max_players})")
        return True

    def leave_lobby(self, lobby_id: str, player_id: str) -> bool:
        """
        Remove player from lobby.

        Args:
            lobby_id: Lobby to leave
            player_id: Player identifier

        Returns:
            True if successful, False otherwise
        """
        lobby = self._lobbies.get(lobby_id)
        if not lobby or player_id not in lobby.members:
            return False

        # Remove member
        del lobby.members[player_id]
        logger.info(f"Player {player_id} left lobby {lobby_id} ({lobby.get_member_count()} remaining)")

        # Handle host leaving
        if lobby.is_host(player_id):
            if lobby.members:
                old_host = player_id
                lobby.transfer_host()
                logger.info(f"Host transferred from {old_host} to {lobby.host_player_id} in lobby {lobby_id}")
            else:
                # No members left - disband lobby
                logger.info(f"Lobby {lobby_id} empty, disbanding")
                lobby.status = LobbyStatus.DISBANDED
                self._cleanup_lobby(lobby_id)

        return True

    def add_bot_to_lobby(
        self,
        lobby_id: str,
        bot_id: int,
        bot_code: str,
        bot_class_name: str,
        owner_username: str
    ) -> Optional[str]:
        """
        Add bot to lobby.

        Args:
            lobby_id: Lobby to join
            bot_id: Database bot ID
            bot_code: Bot source code
            bot_class_name: Bot class name
            owner_username: Bot owner's username

        Returns:
            Bot's player_id if successful, None otherwise
        """
        lobby = self._lobbies.get(lobby_id)
        if not lobby or lobby.status != LobbyStatus.WAITING:
            logger.warning(f"Cannot add bot to lobby {lobby_id} (not found or wrong status)")
            return None

        if lobby.is_full():
            logger.warning(f"Cannot add bot to full lobby {lobby_id}")
            return None

        # Create unique bot player ID
        bot_player_id = f"bot-{owner_username}-{bot_id}"

        if bot_player_id in lobby.members:
            logger.debug(f"Bot {bot_player_id} already in lobby {lobby_id}")
            return None  # Bot already added

        lobby.members[bot_player_id] = LobbyMember(
            player_id=bot_player_id,
            username=f"{owner_username}'s bot",
            is_bot=True,
            bot_id=bot_id,
            bot_code=bot_code,
            bot_class_name=bot_class_name,
            ready=True  # Bots always ready
        )
        logger.info(f"Added bot {bot_player_id} to lobby {lobby_id}")
        return bot_player_id

    def update_settings(
        self,
        lobby_id: str,
        player_id: str,
        settings: LobbySettings
    ) -> bool:
        """
        Update lobby settings (host only).

        Args:
            lobby_id: Lobby to update
            player_id: Player attempting update (must be host)
            settings: New settings

        Returns:
            True if successful, False otherwise
        """
        lobby = self._lobbies.get(lobby_id)
        if not lobby or not lobby.is_host(player_id):
            logger.warning(f"Player {player_id} tried to update settings for lobby {lobby_id} (not host or not found)")
            return False

        if lobby.status != LobbyStatus.WAITING:
            logger.warning(f"Cannot update settings for lobby {lobby_id} in status {lobby.status}")
            return False

        lobby.settings = settings
        logger.info(f"Settings updated for lobby {lobby_id}: difficulty={settings.track_difficulty}, seed={settings.track_seed}, max={settings.max_players}")
        return True

    def start_race(self, lobby_id: str, player_id: str) -> Optional[Tuple[str, Track]]:
        """
        Start race (host only).

        Generates track and transitions lobby to STARTING.

        Args:
            lobby_id: Lobby to start
            player_id: Player attempting start (must be host)

        Returns:
            Tuple of (game_session_id, track) if successful, None otherwise
        """
        lobby = self._lobbies.get(lobby_id)
        if not lobby:
            logger.warning(f"Cannot start race for non-existent lobby {lobby_id}")
            return None

        if not lobby.is_host(player_id):
            logger.warning(f"Player {player_id} tried to start race in lobby {lobby_id} (not host)")
            return None

        if not lobby.can_start_race():
            logger.warning(f"Cannot start race for lobby {lobby_id} (status={lobby.status}, members={lobby.get_member_count()})")
            return None

        # Generate track
        generator = TrackGenerator(seed=lobby.settings.track_seed)
        track = generator.generate(difficulty=lobby.settings.track_difficulty)
        lobby.track = track

        # Create game session ID
        game_session_id = str(uuid4())
        lobby.game_session_id = game_session_id

        # Transition to STARTING (will move to RACING once GameEngine created)
        lobby.status = LobbyStatus.STARTING

        logger.info(f"Starting race for lobby {lobby_id}: session={game_session_id}, members={lobby.get_member_count()}")
        return (game_session_id, track)

    def transition_to_racing(self, lobby_id: str) -> bool:
        """
        Transition lobby from STARTING to RACING.

        Args:
            lobby_id: Lobby identifier

        Returns:
            True if successful, False otherwise
        """
        lobby = self._lobbies.get(lobby_id)
        if not lobby or lobby.status != LobbyStatus.STARTING:
            return False

        lobby.status = LobbyStatus.RACING
        logger.info(f"Lobby {lobby_id} transitioned to RACING")
        return True

    def finish_race(self, lobby_id: str) -> bool:
        """
        Transition lobby from RACING to FINISHED.

        Args:
            lobby_id: Lobby identifier

        Returns:
            True if successful, False otherwise
        """
        lobby = self._lobbies.get(lobby_id)
        if not lobby or lobby.status != LobbyStatus.RACING:
            return False

        lobby.status = LobbyStatus.FINISHED
        logger.info(f"Lobby {lobby_id} race finished")
        return True

    def reset_lobby(self, lobby_id: str, player_id: str) -> bool:
        """
        Reset lobby back to WAITING (host only, from FINISHED).

        Args:
            lobby_id: Lobby to reset
            player_id: Player attempting reset (must be host)

        Returns:
            True if successful, False otherwise
        """
        lobby = self._lobbies.get(lobby_id)
        if not lobby or not lobby.is_host(player_id):
            return False

        if lobby.status != LobbyStatus.FINISHED:
            return False

        lobby.status = LobbyStatus.WAITING
        lobby.game_session_id = None
        lobby.track = None

        # Reset all members' ready status
        for member in lobby.members.values():
            if not member.is_bot:
                member.ready = False

        logger.info(f"Lobby {lobby_id} reset to WAITING")
        return True

    def disband_lobby(self, lobby_id: str, player_id: str) -> bool:
        """
        Disband lobby (host only).

        Args:
            lobby_id: Lobby to disband
            player_id: Player attempting disband (must be host)

        Returns:
            True if successful, False otherwise
        """
        lobby = self._lobbies.get(lobby_id)
        if not lobby or not lobby.is_host(player_id):
            logger.warning(f"Player {player_id} tried to disband lobby {lobby_id} (not host or not found)")
            return False

        lobby.status = LobbyStatus.DISBANDED
        self._cleanup_lobby(lobby_id)
        logger.info(f"Lobby {lobby_id} disbanded by host {player_id}")
        return True

    def _cleanup_lobby(self, lobby_id: str) -> None:
        """
        Remove lobby from memory.

        Args:
            lobby_id: Lobby to clean up
        """
        if lobby_id in self._lobbies:
            lobby = self._lobbies[lobby_id]
            # Remove join code mapping
            if lobby.join_code in self._join_codes:
                del self._join_codes[lobby.join_code]
            del self._lobbies[lobby_id]
            logger.debug(f"Cleaned up lobby {lobby_id}")

    async def cleanup_stale_lobbies(self, max_age_seconds: int = 3600) -> int:
        """
        Clean up lobbies older than max_age_seconds.

        Args:
            max_age_seconds: Maximum age before cleanup (default: 1 hour)

        Returns:
            Number of lobbies cleaned up
        """
        async with self._lock:
            now = time.time()
            to_cleanup = []

            for lobby_id, lobby in self._lobbies.items():
                age = now - lobby.created_at

                # Clean up old lobbies or disbanded lobbies
                if age > max_age_seconds or lobby.status == LobbyStatus.DISBANDED:
                    to_cleanup.append(lobby_id)

            for lobby_id in to_cleanup:
                self._cleanup_lobby(lobby_id)

            if to_cleanup:
                logger.info(f"Cleaned up {len(to_cleanup)} stale lobbies")

            return len(to_cleanup)


# Global lobby manager instance
_lobby_manager = LobbyManager()


def get_lobby_manager() -> LobbyManager:
    """Get global lobby manager instance."""
    return _lobby_manager
