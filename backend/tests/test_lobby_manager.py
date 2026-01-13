"""
Unit tests for lobby system (lobby.py + lobby_manager.py).

Tests lobby creation, joining, leaving, host transfer, bot management,
settings updates, race start, and state transitions.
"""

import pytest
from app.core.lobby import Lobby, LobbyStatus, LobbySettings, LobbyMember
from app.core.lobby_manager import LobbyManager, get_lobby_manager
from app.core.track import TrackGenerator


class TestLobbyDataStructures:
    """Test Lobby, LobbySettings, and LobbyMember dataclasses."""

    def test_lobby_settings_defaults(self):
        """Test LobbySettings has correct defaults."""
        settings = LobbySettings()
        assert settings.track_difficulty == "medium"
        assert settings.track_seed is None
        assert settings.max_players == 8
        assert settings.finish_grace_period == 30

    def test_lobby_member_defaults(self):
        """Test LobbyMember has correct defaults."""
        member = LobbyMember(player_id="player1")
        assert member.player_id == "player1"
        assert member.username is None
        assert member.is_bot is False
        assert member.bot_id is None
        assert member.ready is False
        assert member.connection_time > 0

    def test_lobby_is_host(self):
        """Test Lobby.is_host() method."""
        lobby = Lobby(
            lobby_id="lobby1",
            name="Test Lobby",
            host_player_id="player1",
            settings=LobbySettings(),
            members={}
        )
        assert lobby.is_host("player1") is True
        assert lobby.is_host("player2") is False

    def test_lobby_is_full(self):
        """Test Lobby.is_full() method."""
        settings = LobbySettings(max_players=2)
        lobby = Lobby(
            lobby_id="lobby1",
            name="Test Lobby",
            host_player_id="player1",
            settings=settings,
            members={
                "player1": LobbyMember(player_id="player1"),
                "player2": LobbyMember(player_id="player2")
            }
        )
        assert lobby.is_full() is True

        # Remove one member
        del lobby.members["player2"]
        assert lobby.is_full() is False

    def test_lobby_can_start_race(self):
        """Test Lobby.can_start_race() conditions."""
        lobby = Lobby(
            lobby_id="lobby1",
            name="Test Lobby",
            host_player_id="player1",
            settings=LobbySettings(),
            members={"player1": LobbyMember(player_id="player1")}
        )

        # Can start with host present and WAITING status
        assert lobby.can_start_race() is True

        # Cannot start if host not in members
        lobby.members = {}
        assert lobby.can_start_race() is False

        # Cannot start if status not WAITING
        lobby.members = {"player1": LobbyMember(player_id="player1")}
        lobby.status = LobbyStatus.RACING
        assert lobby.can_start_race() is False

    def test_lobby_transfer_host(self):
        """Test Lobby.transfer_host() method."""
        lobby = Lobby(
            lobby_id="lobby1",
            name="Test Lobby",
            host_player_id="player1",
            settings=LobbySettings(),
            members={
                "player2": LobbyMember(player_id="player2"),
                "player3": LobbyMember(player_id="player3")
            }
        )

        lobby.transfer_host()

        # Host should be transferred to first member (dict insertion order)
        assert lobby.host_player_id == "player2"


class TestLobbyManager:
    """Test LobbyManager class."""

    @pytest.fixture
    def manager(self):
        """Create fresh LobbyManager for each test."""
        return LobbyManager()

    def test_create_lobby(self, manager):
        """Test creating a new lobby."""
        lobby = manager.create_lobby(
            name="Test Lobby",
            host_player_id="player1"
        )

        assert lobby.name == "Test Lobby"
        assert lobby.host_player_id == "player1"
        assert lobby.status == LobbyStatus.WAITING
        assert len(lobby.members) == 1
        assert "player1" in lobby.members
        assert lobby.members["player1"].ready is True  # Host auto-ready

    def test_create_lobby_with_custom_settings(self, manager):
        """Test creating lobby with custom settings."""
        settings = LobbySettings(
            track_difficulty="hard",
            track_seed=12345,
            max_players=4
        )
        lobby = manager.create_lobby(
            name="Hard Lobby",
            host_player_id="player1",
            settings=settings
        )

        assert lobby.settings.track_difficulty == "hard"
        assert lobby.settings.track_seed == 12345
        assert lobby.settings.max_players == 4

    def test_get_lobby(self, manager):
        """Test getting lobby by ID."""
        lobby = manager.create_lobby(
            name="Test Lobby",
            host_player_id="player1"
        )

        retrieved = manager.get_lobby(lobby.lobby_id)
        assert retrieved is not None
        assert retrieved.lobby_id == lobby.lobby_id
        assert retrieved.name == "Test Lobby"

        # Non-existent lobby
        assert manager.get_lobby("invalid-id") is None

    def test_list_lobbies(self, manager):
        """Test listing lobbies."""
        lobby1 = manager.create_lobby("Lobby 1", "player1")
        lobby2 = manager.create_lobby("Lobby 2", "player2")
        lobby3 = manager.create_lobby("Lobby 3", "player3")

        # List all lobbies
        all_lobbies = manager.list_lobbies()
        assert len(all_lobbies) == 3

        # Lobbies sorted by created_at (newest first)
        assert all_lobbies[0].lobby_id == lobby3.lobby_id
        assert all_lobbies[1].lobby_id == lobby2.lobby_id
        assert all_lobbies[2].lobby_id == lobby1.lobby_id

    def test_list_lobbies_with_filter(self, manager):
        """Test listing lobbies filtered by status."""
        lobby1 = manager.create_lobby("Lobby 1", "player1")
        lobby2 = manager.create_lobby("Lobby 2", "player2")
        lobby3 = manager.create_lobby("Lobby 3", "player3")

        # Start one lobby
        lobby2.status = LobbyStatus.RACING

        # Filter by WAITING
        waiting = manager.list_lobbies(status_filter=LobbyStatus.WAITING)
        assert len(waiting) == 2
        assert lobby2.lobby_id not in [l.lobby_id for l in waiting]

        # Filter by RACING
        racing = manager.list_lobbies(status_filter=LobbyStatus.RACING)
        assert len(racing) == 1
        assert racing[0].lobby_id == lobby2.lobby_id

    def test_join_lobby(self, manager):
        """Test player joining a lobby."""
        lobby = manager.create_lobby("Test Lobby", "player1")

        # Player 2 joins
        result = manager.join_lobby(lobby.lobby_id, "player2", username="Alice")
        assert result is True

        retrieved = manager.get_lobby(lobby.lobby_id)
        assert len(retrieved.members) == 2
        assert "player2" in retrieved.members
        assert retrieved.members["player2"].username == "Alice"
        assert retrieved.members["player2"].ready is False  # Non-host not auto-ready

    def test_join_lobby_already_member(self, manager):
        """Test joining lobby when already a member."""
        lobby = manager.create_lobby("Test Lobby", "player1")
        manager.join_lobby(lobby.lobby_id, "player2")

        # Try to join again
        result = manager.join_lobby(lobby.lobby_id, "player2")
        assert result is True  # Already joined returns True

        retrieved = manager.get_lobby(lobby.lobby_id)
        assert len(retrieved.members) == 2  # Still 2 members

    def test_join_full_lobby(self, manager):
        """Test joining a lobby that is full."""
        settings = LobbySettings(max_players=2)
        lobby = manager.create_lobby("Full Lobby", "player1", settings)

        # Fill lobby
        manager.join_lobby(lobby.lobby_id, "player2")

        # Try to join when full
        result = manager.join_lobby(lobby.lobby_id, "player3")
        assert result is False

        retrieved = manager.get_lobby(lobby.lobby_id)
        assert len(retrieved.members) == 2
        assert "player3" not in retrieved.members

    def test_join_lobby_wrong_status(self, manager):
        """Test joining lobby in non-WAITING status."""
        lobby = manager.create_lobby("Test Lobby", "player1")
        lobby.status = LobbyStatus.RACING

        result = manager.join_lobby(lobby.lobby_id, "player2")
        assert result is False

    def test_join_nonexistent_lobby(self, manager):
        """Test joining a lobby that doesn't exist."""
        result = manager.join_lobby("invalid-id", "player1")
        assert result is False

    def test_leave_lobby(self, manager):
        """Test player leaving a lobby."""
        lobby = manager.create_lobby("Test Lobby", "player1")
        manager.join_lobby(lobby.lobby_id, "player2")

        # Player 2 leaves
        result = manager.leave_lobby(lobby.lobby_id, "player2")
        assert result is True

        retrieved = manager.get_lobby(lobby.lobby_id)
        assert len(retrieved.members) == 1
        assert "player2" not in retrieved.members

    def test_host_leaves_transfers_host(self, manager):
        """Test that host leaving transfers host to another member."""
        lobby = manager.create_lobby("Test Lobby", "player1")
        manager.join_lobby(lobby.lobby_id, "player2")
        manager.join_lobby(lobby.lobby_id, "player3")

        # Host leaves
        result = manager.leave_lobby(lobby.lobby_id, "player1")
        assert result is True

        retrieved = manager.get_lobby(lobby.lobby_id)
        assert retrieved.host_player_id != "player1"
        assert retrieved.host_player_id in ["player2", "player3"]
        assert len(retrieved.members) == 2

    def test_last_member_leaves_disbands_lobby(self, manager):
        """Test that lobby is disbanded when last member leaves."""
        lobby = manager.create_lobby("Test Lobby", "player1")

        # Host leaves (only member)
        result = manager.leave_lobby(lobby.lobby_id, "player1")
        assert result is True

        # Lobby should be cleaned up
        retrieved = manager.get_lobby(lobby.lobby_id)
        assert retrieved is None

    def test_leave_lobby_not_member(self, manager):
        """Test leaving lobby when not a member."""
        lobby = manager.create_lobby("Test Lobby", "player1")

        result = manager.leave_lobby(lobby.lobby_id, "player2")
        assert result is False

    def test_add_bot_to_lobby(self, manager):
        """Test adding a bot to a lobby."""
        lobby = manager.create_lobby("Test Lobby", "player1")

        bot_code = "class MyBot:\n    def on_tick(self, state):\n        return {'accelerate': True}"
        bot_player_id = manager.add_bot_to_lobby(
            lobby_id=lobby.lobby_id,
            bot_id=42,
            bot_code=bot_code,
            bot_class_name="MyBot",
            owner_username="Alice"
        )

        assert bot_player_id is not None
        assert bot_player_id.startswith("bot-Alice-42")

        retrieved = manager.get_lobby(lobby.lobby_id)
        assert len(retrieved.members) == 2
        assert bot_player_id in retrieved.members
        assert retrieved.members[bot_player_id].is_bot is True
        assert retrieved.members[bot_player_id].bot_id == 42
        assert retrieved.members[bot_player_id].bot_code == bot_code
        assert retrieved.members[bot_player_id].ready is True  # Bots auto-ready

    def test_add_bot_to_full_lobby(self, manager):
        """Test adding bot to full lobby."""
        settings = LobbySettings(max_players=2)
        lobby = manager.create_lobby("Full Lobby", "player1", settings)
        manager.join_lobby(lobby.lobby_id, "player2")

        # Try to add bot when full
        result = manager.add_bot_to_lobby(
            lobby_id=lobby.lobby_id,
            bot_id=42,
            bot_code="code",
            bot_class_name="Bot",
            owner_username="Alice"
        )

        assert result is None

    def test_add_duplicate_bot(self, manager):
        """Test adding same bot twice."""
        lobby = manager.create_lobby("Test Lobby", "player1")

        # Add bot first time
        bot_player_id = manager.add_bot_to_lobby(
            lobby_id=lobby.lobby_id,
            bot_id=42,
            bot_code="code",
            bot_class_name="Bot",
            owner_username="Alice"
        )
        assert bot_player_id is not None

        # Try to add same bot again
        result = manager.add_bot_to_lobby(
            lobby_id=lobby.lobby_id,
            bot_id=42,
            bot_code="code",
            bot_class_name="Bot",
            owner_username="Alice"
        )
        assert result is None  # Already added

    def test_update_settings_by_host(self, manager):
        """Test host updating lobby settings."""
        lobby = manager.create_lobby("Test Lobby", "player1")

        new_settings = LobbySettings(
            track_difficulty="extreme",
            track_seed=99999,
            max_players=4
        )

        result = manager.update_settings(lobby.lobby_id, "player1", new_settings)
        assert result is True

        retrieved = manager.get_lobby(lobby.lobby_id)
        assert retrieved.settings.track_difficulty == "extreme"
        assert retrieved.settings.track_seed == 99999
        assert retrieved.settings.max_players == 4

    def test_update_settings_by_non_host(self, manager):
        """Test non-host trying to update settings."""
        lobby = manager.create_lobby("Test Lobby", "player1")
        manager.join_lobby(lobby.lobby_id, "player2")

        new_settings = LobbySettings(track_difficulty="extreme")

        result = manager.update_settings(lobby.lobby_id, "player2", new_settings)
        assert result is False

        # Settings unchanged
        retrieved = manager.get_lobby(lobby.lobby_id)
        assert retrieved.settings.track_difficulty == "medium"

    def test_update_settings_wrong_status(self, manager):
        """Test updating settings in non-WAITING status."""
        lobby = manager.create_lobby("Test Lobby", "player1")
        lobby.status = LobbyStatus.RACING

        new_settings = LobbySettings(track_difficulty="extreme")
        result = manager.update_settings(lobby.lobby_id, "player1", new_settings)
        assert result is False

    def test_start_race_by_host(self, manager):
        """Test host starting a race."""
        lobby = manager.create_lobby("Test Lobby", "player1")
        manager.join_lobby(lobby.lobby_id, "player2")

        result = manager.start_race(lobby.lobby_id, "player1")

        assert result is not None
        game_session_id, track = result
        assert game_session_id is not None
        assert track is not None

        retrieved = manager.get_lobby(lobby.lobby_id)
        assert retrieved.status == LobbyStatus.STARTING
        assert retrieved.game_session_id == game_session_id
        assert retrieved.track is not None

    def test_start_race_by_non_host(self, manager):
        """Test non-host trying to start race."""
        lobby = manager.create_lobby("Test Lobby", "player1")
        manager.join_lobby(lobby.lobby_id, "player2")

        result = manager.start_race(lobby.lobby_id, "player2")
        assert result is None

        retrieved = manager.get_lobby(lobby.lobby_id)
        assert retrieved.status == LobbyStatus.WAITING

    def test_start_race_with_seed(self, manager):
        """Test starting race with specific seed generates consistent track."""
        settings = LobbySettings(track_seed=12345)
        lobby = manager.create_lobby("Test Lobby", "player1", settings)

        result = manager.start_race(lobby.lobby_id, "player1")
        assert result is not None

        _, track1 = result

        # Create another lobby with same seed
        lobby2 = manager.create_lobby("Test Lobby 2", "player3", settings)
        result2 = manager.start_race(lobby2.lobby_id, "player3")
        _, track2 = result2

        # Tracks should be identical
        assert len(track1.segments) == len(track2.segments)
        assert len(track1.checkpoints) == len(track2.checkpoints)

    def test_transition_to_racing(self, manager):
        """Test transitioning lobby from STARTING to RACING."""
        lobby = manager.create_lobby("Test Lobby", "player1")
        manager.start_race(lobby.lobby_id, "player1")

        result = manager.transition_to_racing(lobby.lobby_id)
        assert result is True

        retrieved = manager.get_lobby(lobby.lobby_id)
        assert retrieved.status == LobbyStatus.RACING

    def test_transition_to_racing_wrong_status(self, manager):
        """Test transitioning to RACING from wrong status."""
        lobby = manager.create_lobby("Test Lobby", "player1")

        # Try to transition from WAITING (should be STARTING)
        result = manager.transition_to_racing(lobby.lobby_id)
        assert result is False

    def test_finish_race(self, manager):
        """Test finishing a race."""
        lobby = manager.create_lobby("Test Lobby", "player1")
        manager.start_race(lobby.lobby_id, "player1")
        manager.transition_to_racing(lobby.lobby_id)

        result = manager.finish_race(lobby.lobby_id)
        assert result is True

        retrieved = manager.get_lobby(lobby.lobby_id)
        assert retrieved.status == LobbyStatus.FINISHED

    def test_finish_race_wrong_status(self, manager):
        """Test finishing race from wrong status."""
        lobby = manager.create_lobby("Test Lobby", "player1")

        result = manager.finish_race(lobby.lobby_id)
        assert result is False

    def test_reset_lobby(self, manager):
        """Test resetting lobby after race."""
        lobby = manager.create_lobby("Test Lobby", "player1")
        manager.join_lobby(lobby.lobby_id, "player2")
        manager.start_race(lobby.lobby_id, "player1")
        manager.transition_to_racing(lobby.lobby_id)
        manager.finish_race(lobby.lobby_id)

        result = manager.reset_lobby(lobby.lobby_id, "player1")
        assert result is True

        retrieved = manager.get_lobby(lobby.lobby_id)
        assert retrieved.status == LobbyStatus.WAITING
        assert retrieved.game_session_id is None
        assert retrieved.track is None

        # Human players reset to not ready, bots stay ready
        assert retrieved.members["player1"].ready is False
        assert retrieved.members["player2"].ready is False

    def test_reset_lobby_by_non_host(self, manager):
        """Test non-host trying to reset lobby."""
        lobby = manager.create_lobby("Test Lobby", "player1")
        manager.join_lobby(lobby.lobby_id, "player2")
        lobby.status = LobbyStatus.FINISHED

        result = manager.reset_lobby(lobby.lobby_id, "player2")
        assert result is False

    def test_reset_lobby_with_bots(self, manager):
        """Test that bots stay ready after reset."""
        lobby = manager.create_lobby("Test Lobby", "player1")
        bot_id = manager.add_bot_to_lobby(
            lobby_id=lobby.lobby_id,
            bot_id=42,
            bot_code="code",
            bot_class_name="Bot",
            owner_username="Alice"
        )
        lobby.status = LobbyStatus.FINISHED

        manager.reset_lobby(lobby.lobby_id, "player1")

        retrieved = manager.get_lobby(lobby.lobby_id)
        assert retrieved.members["player1"].ready is False  # Human reset
        assert retrieved.members[bot_id].ready is True  # Bot stays ready

    def test_disband_lobby_by_host(self, manager):
        """Test host disbanding a lobby."""
        lobby = manager.create_lobby("Test Lobby", "player1")
        manager.join_lobby(lobby.lobby_id, "player2")

        result = manager.disband_lobby(lobby.lobby_id, "player1")
        assert result is True

        # Lobby should be cleaned up
        retrieved = manager.get_lobby(lobby.lobby_id)
        assert retrieved is None

    def test_disband_lobby_by_non_host(self, manager):
        """Test non-host trying to disband lobby."""
        lobby = manager.create_lobby("Test Lobby", "player1")
        manager.join_lobby(lobby.lobby_id, "player2")

        result = manager.disband_lobby(lobby.lobby_id, "player2")
        assert result is False

        # Lobby still exists
        retrieved = manager.get_lobby(lobby.lobby_id)
        assert retrieved is not None

    @pytest.mark.asyncio
    async def test_cleanup_stale_lobbies(self, manager):
        """Test cleanup of old lobbies."""
        import time

        # Create old lobby (simulate by setting created_at in past)
        lobby1 = manager.create_lobby("Old Lobby", "player1")
        lobby1.created_at = time.time() - 7200  # 2 hours ago

        # Create new lobby
        lobby2 = manager.create_lobby("New Lobby", "player2")

        # Clean up lobbies older than 1 hour
        count = await manager.cleanup_stale_lobbies(max_age_seconds=3600)

        assert count == 1
        assert manager.get_lobby(lobby1.lobby_id) is None
        assert manager.get_lobby(lobby2.lobby_id) is not None

    @pytest.mark.asyncio
    async def test_cleanup_disbanded_lobbies(self, manager):
        """Test cleanup of disbanded lobbies."""
        lobby1 = manager.create_lobby("Test Lobby 1", "player1")
        lobby2 = manager.create_lobby("Test Lobby 2", "player2")

        # Disband lobby1
        lobby1.status = LobbyStatus.DISBANDED

        # Cleanup should remove disbanded
        count = await manager.cleanup_stale_lobbies(max_age_seconds=3600)

        assert count == 1
        assert manager.get_lobby(lobby1.lobby_id) is None
        assert manager.get_lobby(lobby2.lobby_id) is not None


class TestGlobalLobbyManager:
    """Test global lobby manager singleton."""

    def test_get_lobby_manager_returns_singleton(self):
        """Test that get_lobby_manager returns same instance."""
        manager1 = get_lobby_manager()
        manager2 = get_lobby_manager()

        assert manager1 is manager2

        # Create lobby in manager1, should appear in manager2
        lobby = manager1.create_lobby("Test", "player1")
        assert manager2.get_lobby(lobby.lobby_id) is not None
