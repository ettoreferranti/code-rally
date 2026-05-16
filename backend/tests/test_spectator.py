"""
Unit tests for spectator mode (issue #127).

Tests spectator joining, lobby spectator tracking, spectator count,
and ensuring spectators don't affect game state.
"""

import pytest
from app.core.lobby import Lobby, LobbyStatus, LobbySettings, LobbyMember
from app.core.lobby_manager import LobbyManager


class TestLobbySpectatorDataStructures:
    """Test spectator-related fields and methods on Lobby dataclass."""

    def _make_lobby(self, **kwargs) -> Lobby:
        """Helper to create a lobby with defaults."""
        defaults = {
            'lobby_id': 'lobby1',
            'join_code': 'TEST-CODE-01',
            'name': 'Test Lobby',
            'host_player_id': 'host',
            'settings': LobbySettings(),
            'members': {
                'host': LobbyMember(player_id='host', ready=True)
            },
        }
        defaults.update(kwargs)
        return Lobby(**defaults)

    def test_lobby_has_spectators_dict(self):
        """Test that Lobby has a spectators dict, defaulting to empty."""
        lobby = self._make_lobby()
        assert hasattr(lobby, 'spectators')
        assert isinstance(lobby.spectators, dict)
        assert len(lobby.spectators) == 0

    def test_spectator_count_empty(self):
        """Test get_spectator_count returns 0 when no spectators."""
        lobby = self._make_lobby()
        assert lobby.get_spectator_count() == 0

    def test_spectator_count_with_spectators(self):
        """Test get_spectator_count returns correct count."""
        lobby = self._make_lobby()
        lobby.spectators['spec1'] = LobbyMember(player_id='spec1')
        lobby.spectators['spec2'] = LobbyMember(player_id='spec2')
        assert lobby.get_spectator_count() == 2

    def test_spectators_not_counted_in_member_count(self):
        """Test that spectators don't affect get_member_count."""
        lobby = self._make_lobby()
        lobby.spectators['spec1'] = LobbyMember(player_id='spec1')
        assert lobby.get_member_count() == 1  # Only the host

    def test_spectators_not_counted_in_is_full(self):
        """Test that spectators don't affect is_full check."""
        lobby = self._make_lobby(
            settings=LobbySettings(max_players=2)
        )
        lobby.members['player2'] = LobbyMember(player_id='player2')
        # Lobby is full (2/2 members)
        assert lobby.is_full() is True
        # Adding spectators shouldn't change that
        lobby.spectators['spec1'] = LobbyMember(player_id='spec1')
        assert lobby.is_full() is True

    def test_spectators_dont_affect_can_start_race(self):
        """Test that spectators don't affect can_start_race."""
        lobby = self._make_lobby()
        assert lobby.can_start_race() is True
        # Adding spectators shouldn't change result
        lobby.spectators['spec1'] = LobbyMember(player_id='spec1')
        assert lobby.can_start_race() is True

    def test_spectators_not_affected_by_host_transfer(self):
        """Test that transfer_host only considers members, not spectators."""
        lobby = self._make_lobby()
        lobby.members['player2'] = LobbyMember(player_id='player2')
        lobby.spectators['spec1'] = LobbyMember(player_id='spec1')
        # Remove host from members
        del lobby.members['host']
        lobby.transfer_host()
        assert lobby.host_player_id == 'player2'  # Not spec1


class TestLobbyManagerSpectators:
    """Test LobbyManager spectator methods."""

    def setup_method(self):
        """Create fresh LobbyManager for each test."""
        self.manager = LobbyManager()

    def _create_lobby(self, **kwargs) -> Lobby:
        """Helper to create a lobby via the manager."""
        defaults = {
            'name': 'Test Lobby',
            'host_player_id': 'host',
        }
        defaults.update(kwargs)
        return self.manager.create_lobby(**defaults)

    def test_spectate_waiting_lobby(self):
        """Test spectator can join a WAITING lobby."""
        lobby = self._create_lobby()
        result = self.manager.spectate_lobby(lobby.lobby_id, 'spec1', 'Spectator1')
        assert result is True
        assert 'spec1' in lobby.spectators
        assert lobby.spectators['spec1'].username == 'Spectator1'

    def test_spectate_racing_lobby(self):
        """Test spectator can join a RACING lobby."""
        lobby = self._create_lobby()
        lobby.status = LobbyStatus.RACING
        result = self.manager.spectate_lobby(lobby.lobby_id, 'spec1')
        assert result is True
        assert 'spec1' in lobby.spectators

    def test_spectate_starting_lobby(self):
        """Test spectator can join a STARTING lobby."""
        lobby = self._create_lobby()
        lobby.status = LobbyStatus.STARTING
        result = self.manager.spectate_lobby(lobby.lobby_id, 'spec1')
        assert result is True
        assert 'spec1' in lobby.spectators

    def test_spectate_finished_lobby_rejected(self):
        """Test spectator cannot join a FINISHED lobby."""
        lobby = self._create_lobby()
        lobby.status = LobbyStatus.FINISHED
        result = self.manager.spectate_lobby(lobby.lobby_id, 'spec1')
        assert result is False
        assert 'spec1' not in lobby.spectators

    def test_spectate_disbanded_lobby_rejected(self):
        """Test spectator cannot join a DISBANDED lobby."""
        lobby = self._create_lobby()
        lobby.status = LobbyStatus.DISBANDED
        result = self.manager.spectate_lobby(lobby.lobby_id, 'spec1')
        assert result is False

    def test_spectate_nonexistent_lobby(self):
        """Test spectating a nonexistent lobby returns False."""
        result = self.manager.spectate_lobby('nonexistent', 'spec1')
        assert result is False

    def test_spectator_already_spectating(self):
        """Test that spectating again returns True (idempotent)."""
        lobby = self._create_lobby()
        self.manager.spectate_lobby(lobby.lobby_id, 'spec1')
        result = self.manager.spectate_lobby(lobby.lobby_id, 'spec1')
        assert result is True
        assert lobby.get_spectator_count() == 1

    def test_remove_spectator(self):
        """Test removing a spectator from lobby."""
        lobby = self._create_lobby()
        self.manager.spectate_lobby(lobby.lobby_id, 'spec1')
        assert lobby.get_spectator_count() == 1

        result = self.manager.remove_spectator(lobby.lobby_id, 'spec1')
        assert result is True
        assert lobby.get_spectator_count() == 0

    def test_remove_spectator_not_found(self):
        """Test removing a spectator that doesn't exist."""
        lobby = self._create_lobby()
        result = self.manager.remove_spectator(lobby.lobby_id, 'spec1')
        assert result is False

    def test_remove_spectator_nonexistent_lobby(self):
        """Test removing spectator from nonexistent lobby."""
        result = self.manager.remove_spectator('nonexistent', 'spec1')
        assert result is False

    def test_spectator_leave_does_not_transfer_host(self):
        """Test that spectator leaving doesn't trigger host transfer."""
        lobby = self._create_lobby()
        self.manager.spectate_lobby(lobby.lobby_id, 'spec1')
        self.manager.remove_spectator(lobby.lobby_id, 'spec1')
        assert lobby.host_player_id == 'host'
        assert lobby.status == LobbyStatus.WAITING

    def test_spectator_leave_does_not_disband(self):
        """Test that spectator leaving doesn't disband the lobby."""
        lobby = self._create_lobby()
        self.manager.spectate_lobby(lobby.lobby_id, 'spec1')
        self.manager.remove_spectator(lobby.lobby_id, 'spec1')
        # Lobby should still exist with its host
        assert self.manager.get_lobby(lobby.lobby_id) is not None
        assert lobby.status == LobbyStatus.WAITING

    def test_spectator_not_added_as_member(self):
        """Test that spectating does not add to members dict."""
        lobby = self._create_lobby()
        self.manager.spectate_lobby(lobby.lobby_id, 'spec1')
        assert 'spec1' not in lobby.members
        assert lobby.get_member_count() == 1  # Only host

    def test_multiple_spectators(self):
        """Test multiple spectators can join."""
        lobby = self._create_lobby()
        for i in range(10):
            result = self.manager.spectate_lobby(lobby.lobby_id, f'spec{i}')
            assert result is True
        assert lobby.get_spectator_count() == 10
        # Members count unaffected
        assert lobby.get_member_count() == 1

    def test_spectator_does_not_fill_lobby(self):
        """Test that spectators don't count toward max_players."""
        lobby = self._create_lobby(settings=LobbySettings(max_players=2))
        # Add spectators
        for i in range(5):
            self.manager.spectate_lobby(lobby.lobby_id, f'spec{i}')
        # Lobby should not be full (only 1 member)
        assert lobby.is_full() is False
        # Can still add a real player
        result = self.manager.join_lobby(lobby.lobby_id, 'player2')
        assert result is True
