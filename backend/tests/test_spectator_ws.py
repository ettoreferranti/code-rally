"""
Integration tests for spectator WebSocket endpoint (issue #127).

Tests the full WS connection flow for spectators:
- Connecting with spectate=true to a waiting lobby
- Connecting to a non-existent lobby
- Inputs are silently ignored for spectators
- Disconnecting removes spectator from lobby

Unit-level spectator data-structure tests live in test_spectator.py;
this file covers the WebSocket endpoint integration.
"""

import json

import pytest
from fastapi.testclient import TestClient

from main import app
from app.core.lobby_manager import get_lobby_manager


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def reset_lobby_manager():
    manager = get_lobby_manager()
    manager._lobbies.clear()
    yield
    manager._lobbies.clear()


def _create_waiting_lobby(client: TestClient, host: str = "host1", name: str = "Test Lobby") -> str:
    """Helper: create a lobby via REST and return its id."""
    response = client.post("/lobbies", json={"name": name, "host_player_id": host})
    assert response.status_code == 201, response.text
    return response.json()["lobby_id"]


class TestSpectatorWebSocketJoin:
    """Spectator joining a lobby via WS."""

    def test_spectator_connects_to_waiting_lobby(self, client):
        """Spectator connecting to a WAITING lobby receives spectator_joined."""
        lobby_id = _create_waiting_lobby(client)

        with client.websocket_connect(
            f"/game/ws?lobby_id={lobby_id}&player_id=spec1&spectate=true"
        ) as ws:
            message = ws.receive_json()
            assert message["type"] == "spectator_joined"
            assert message["data"]["player_id"] == "spec1"
            lobby_state = message["data"]["lobby"]
            assert lobby_state["lobby_id"] == lobby_id
            assert lobby_state["spectator_count"] == 1

        # After disconnect, spectator should be cleaned up
        manager = get_lobby_manager()
        lobby = manager.get_lobby(lobby_id)
        assert lobby is not None
        assert lobby.get_spectator_count() == 0

    def test_spectator_added_to_lobby_state(self, client):
        """Lobby reflects the spectator while connected."""
        lobby_id = _create_waiting_lobby(client)

        with client.websocket_connect(
            f"/game/ws?lobby_id={lobby_id}&player_id=spec1&spectate=true"
        ) as ws:
            ws.receive_json()  # spectator_joined

            manager = get_lobby_manager()
            lobby = manager.get_lobby(lobby_id)
            assert lobby.get_spectator_count() == 1
            assert "spec1" in lobby.spectators
            # Spectator must not be in members
            assert "spec1" not in lobby.members
            assert lobby.get_member_count() == 1  # Only the host

    def test_multiple_spectators_share_lobby(self, client):
        """Two spectators connecting are both tracked."""
        lobby_id = _create_waiting_lobby(client)

        with client.websocket_connect(
            f"/game/ws?lobby_id={lobby_id}&player_id=spec1&spectate=true"
        ) as ws1:
            ws1.receive_json()  # spectator_joined for spec1
            with client.websocket_connect(
                f"/game/ws?lobby_id={lobby_id}&player_id=spec2&spectate=true"
            ) as ws2:
                ws2.receive_json()  # spectator_joined for spec2

                manager = get_lobby_manager()
                lobby = manager.get_lobby(lobby_id)
                assert lobby.get_spectator_count() == 2
                assert "spec1" in lobby.spectators
                assert "spec2" in lobby.spectators


class TestSpectatorWebSocketErrors:
    """Spectator endpoint error paths."""

    def test_spectator_on_nonexistent_lobby_receives_error(self, client):
        """Spectating a lobby that doesn't exist returns an error message."""
        with client.websocket_connect(
            "/game/ws?lobby_id=does-not-exist&player_id=spec1&spectate=true"
        ) as ws:
            message = ws.receive_json()
            assert message["type"] == "error"
            assert "lobby" in message["data"]["message"].lower()


class TestSpectatorWebSocketInputs:
    """Spectator-side message handling rules."""

    def test_spectator_input_is_silently_ignored(self, client):
        """A spectator sending an 'input' message does not raise or affect state."""
        lobby_id = _create_waiting_lobby(client)

        with client.websocket_connect(
            f"/game/ws?lobby_id={lobby_id}&player_id=spec1&spectate=true"
        ) as ws:
            ws.receive_json()  # spectator_joined

            # Send an input message — should be silently ignored
            ws.send_text(json.dumps({
                "type": "input",
                "data": {
                    "accelerate": True,
                    "brake": False,
                    "turn_left": False,
                    "turn_right": False,
                    "nitro": False,
                },
            }))

            # The connection must still be alive — confirm by sending a pong
            ws.send_text(json.dumps({"type": "pong"}))

            # Spectator is still in the lobby
            manager = get_lobby_manager()
            lobby = manager.get_lobby(lobby_id)
            assert lobby.get_spectator_count() == 1


class TestSpectatorWebSocketDisconnect:
    """Spectator cleanup on disconnect."""

    def test_disconnect_removes_spectator_from_lobby(self, client):
        """Closing the WS removes the spectator from the lobby spectators dict."""
        lobby_id = _create_waiting_lobby(client)

        with client.websocket_connect(
            f"/game/ws?lobby_id={lobby_id}&player_id=spec1&spectate=true"
        ) as ws:
            ws.receive_json()  # spectator_joined
            manager = get_lobby_manager()
            assert manager.get_lobby(lobby_id).get_spectator_count() == 1

        # After context exit (disconnect), spectator must be gone
        manager = get_lobby_manager()
        lobby = manager.get_lobby(lobby_id)
        assert lobby is not None
        assert lobby.get_spectator_count() == 0
        assert "spec1" not in lobby.spectators

    def test_explicit_leave_lobby_removes_spectator(self, client):
        """Sending leave_lobby breaks the loop and cleans up."""
        lobby_id = _create_waiting_lobby(client)

        with client.websocket_connect(
            f"/game/ws?lobby_id={lobby_id}&player_id=spec1&spectate=true"
        ) as ws:
            ws.receive_json()  # spectator_joined
            ws.send_text(json.dumps({"type": "leave_lobby"}))

        manager = get_lobby_manager()
        lobby = manager.get_lobby(lobby_id)
        assert lobby is not None
        assert lobby.get_spectator_count() == 0


class TestSpectatorRacingLobbyGameState:
    """Lobby spectators joining a RACING lobby must be registered for
    the session's game-state broadcast — otherwise their frontend sits
    on a "Waiting for game state..." screen indefinitely (the bug that
    motivated this test class).
    """

    def test_spectator_registered_in_session_pool_for_racing_lobby(self, client):
        """When a spectator opens the WS against a RACING lobby, the
        backend must add their websocket to ``_spectator_connections``
        keyed by the lobby's game_session_id. That's the only path that
        gets them into ``broadcast_game_state``'s send loop.
        """
        from app.api.routes import game as game_route
        from app.core.engine import GameEngine
        from app.core.lobby import LobbyStatus
        from app.core.track import TrackGenerator

        lobby_id = _create_waiting_lobby(client)
        manager = get_lobby_manager()
        lobby = manager.get_lobby(lobby_id)
        lobby.status = LobbyStatus.RACING
        lobby.game_session_id = "session-spec-racing"

        # The WS handler reads engine.state.track from _game_sessions to
        # build the race_starting payload. Stand up a tiny engine for it.
        track = TrackGenerator(seed=42).generate(difficulty="easy")
        engine = GameEngine(track)
        game_route._game_sessions["session-spec-racing"] = engine

        try:
            with client.websocket_connect(
                f"/game/ws?lobby_id={lobby_id}&player_id=spec1&spectate=true"
            ) as ws:
                # First message: spectator_joined.
                first = ws.receive_json()
                assert first["type"] == "spectator_joined"
                # Second message: race_starting with track (because lobby is RACING).
                second = ws.receive_json()
                assert second["type"] == "race_starting"

                # The fix: the websocket must now be in the session's
                # spectator pool so broadcast_game_state reaches it.
                pool = game_route._spectator_connections.get("session-spec-racing")
                assert pool is not None
                assert len(pool) == 1
        finally:
            game_route._game_sessions.pop("session-spec-racing", None)
            game_route._spectator_connections.pop("session-spec-racing", None)

    def test_spectator_removed_from_session_pool_on_disconnect(self, client):
        """Cleanup symmetry: closing the WS must drop the spectator
        from the session's pool too, not just the lobby's spectator dict.
        """
        from app.api.routes import game as game_route
        from app.core.engine import GameEngine
        from app.core.lobby import LobbyStatus
        from app.core.track import TrackGenerator

        lobby_id = _create_waiting_lobby(client)
        manager = get_lobby_manager()
        lobby = manager.get_lobby(lobby_id)
        lobby.status = LobbyStatus.RACING
        lobby.game_session_id = "session-spec-cleanup"

        track = TrackGenerator(seed=42).generate(difficulty="easy")
        engine = GameEngine(track)
        game_route._game_sessions["session-spec-cleanup"] = engine

        try:
            with client.websocket_connect(
                f"/game/ws?lobby_id={lobby_id}&player_id=spec1&spectate=true"
            ) as ws:
                ws.receive_json()  # spectator_joined
                ws.receive_json()  # race_starting

            # After the `with` exits the WS is closed — pool should be
            # cleaned of the websocket (or the key removed entirely).
            pool = game_route._spectator_connections.get("session-spec-cleanup", set())
            assert len(pool) == 0
        finally:
            game_route._game_sessions.pop("session-spec-cleanup", None)
            game_route._spectator_connections.pop("session-spec-cleanup", None)
