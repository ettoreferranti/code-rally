"""
Integration tests for lobby REST API endpoints.

Tests all lobby CRUD operations via HTTP:
- POST /lobbies - Create lobby
- GET /lobbies - List lobbies
- GET /lobbies/{id} - Get lobby details
- PUT /lobbies/{id}/settings - Update settings
- DELETE /lobbies/{id} - Disband lobby
"""

import pytest
from fastapi.testclient import TestClient

from main import app
from app.core.lobby_manager import get_lobby_manager


@pytest.fixture
def client():
    """Create FastAPI test client."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def reset_lobby_manager():
    """Reset lobby manager before each test."""
    # Get the global manager and clear it
    manager = get_lobby_manager()
    manager._lobbies.clear()
    yield


# ===== Lobby leave / WS-disconnect behaviour =====


class TestHandleLeaveLobbyDuringRace:
    """``handle_leave_lobby`` runs both on explicit user leave and on
    lobby WebSocket disconnect. When the disconnect coincides with a
    race start (the frontend navigating from /lobby to /race), we MUST
    NOT remove the player from the lobby — they're in the race, not
    gone, and removal triggers a spurious host transfer (logged as
    "transferred from X to X" when the same player reconnects under
    the same player_id on the race WS).
    """

    @pytest.mark.asyncio
    async def test_disconnect_while_racing_preserves_membership(self, monkeypatch):
        """RACING status: WS close means 'went to race screen', not 'left'."""
        import asyncio  # noqa: F401 — used implicitly by pytest-asyncio
        from app.api.routes import game as game_route
        from app.core.lobby import LobbyStatus

        # Stub the broadcast to avoid pulling in the connection manager.
        broadcast_calls = []

        async def fake_broadcast(lobby_id, message, exclude_player_id=None):
            broadcast_calls.append((lobby_id, message))

        monkeypatch.setattr(game_route, "broadcast_to_lobby", fake_broadcast)

        manager = get_lobby_manager()
        lobby = manager.create_lobby("Race", "host_player")
        manager.join_lobby(lobby.lobby_id, "player_b", username="bee")
        lobby.status = LobbyStatus.RACING

        # Disconnect during race → membership stays intact.
        await game_route.handle_leave_lobby(lobby.lobby_id, "player_b")

        members = manager.get_lobby(lobby.lobby_id).members
        assert "player_b" in members, "membership must be preserved during race"
        # No lobby_member_left broadcast — nobody actually left.
        assert broadcast_calls == []

    @pytest.mark.asyncio
    async def test_disconnect_while_starting_preserves_membership(self, monkeypatch):
        """STARTING covers the race-start window between 'host clicked
        start' and 'lobby transitions to RACING'. Same logic applies.
        """
        from app.api.routes import game as game_route
        from app.core.lobby import LobbyStatus

        async def fake_broadcast(lobby_id, message, exclude_player_id=None):
            pass

        monkeypatch.setattr(game_route, "broadcast_to_lobby", fake_broadcast)

        manager = get_lobby_manager()
        lobby = manager.create_lobby("Race", "host_player")
        manager.join_lobby(lobby.lobby_id, "player_b", username="bee")
        lobby.status = LobbyStatus.STARTING

        await game_route.handle_leave_lobby(lobby.lobby_id, "player_b")

        assert "player_b" in manager.get_lobby(lobby.lobby_id).members

    @pytest.mark.asyncio
    async def test_disconnect_while_waiting_still_removes_member(self, monkeypatch):
        """WAITING: the user really did leave the lobby (or browser
        crashed). The original removal behaviour is intact.
        """
        from app.api.routes import game as game_route

        broadcast_calls = []

        async def fake_broadcast(lobby_id, message, exclude_player_id=None):
            broadcast_calls.append(message)

        monkeypatch.setattr(game_route, "broadcast_to_lobby", fake_broadcast)

        manager = get_lobby_manager()
        lobby = manager.create_lobby("Race", "host_player")
        manager.join_lobby(lobby.lobby_id, "player_b", username="bee")
        # Lobby still in WAITING by default.

        await game_route.handle_leave_lobby(lobby.lobby_id, "player_b")

        assert "player_b" not in manager.get_lobby(lobby.lobby_id).members
        # Broadcast was sent.
        assert any(m["type"] == "lobby_member_left" for m in broadcast_calls)

    @pytest.mark.asyncio
    async def test_disconnect_after_finished_still_removes_member(self, monkeypatch):
        """FINISHED: the race is over; the lobby is in results view. A
        WS close at this point IS the user actually leaving — they're
        navigating away from the post-race screen.
        """
        from app.api.routes import game as game_route
        from app.core.lobby import LobbyStatus

        async def fake_broadcast(lobby_id, message, exclude_player_id=None):
            pass

        monkeypatch.setattr(game_route, "broadcast_to_lobby", fake_broadcast)

        manager = get_lobby_manager()
        lobby = manager.create_lobby("Race", "host_player")
        manager.join_lobby(lobby.lobby_id, "player_b", username="bee")
        lobby.status = LobbyStatus.FINISHED

        await game_route.handle_leave_lobby(lobby.lobby_id, "player_b")

        assert "player_b" not in manager.get_lobby(lobby.lobby_id).members

    @pytest.mark.asyncio
    async def test_broadcast_game_state_propagates_finish_to_lobby(self, monkeypatch):
        """When the engine race ends, the WS broadcaster must flip the
        lobby's status from RACING to FINISHED and broadcast a fresh
        lobby_state. Without this, the lobby browser shows "in race"
        forever after the race actually ends.
        """
        from app.api.routes import game as game_route
        from app.core.engine import GameEngine, RaceStatus
        from app.core.lobby import LobbyStatus
        from app.core.track import TrackGenerator

        # Stub broadcast_to_lobby so we can capture the lobby_state msg.
        captured = []

        async def fake_broadcast(lobby_id, message, exclude_player_id=None):
            captured.append((lobby_id, message))

        monkeypatch.setattr(game_route, "broadcast_to_lobby", fake_broadcast)

        # Set up: a lobby in RACING, with a session registered in
        # _lobby_sessions whose engine is FINISHED.
        manager = get_lobby_manager()
        lobby = manager.create_lobby("Race", "host_player")
        lobby.status = LobbyStatus.RACING
        lobby.game_session_id = "session-finish-test"

        track = TrackGenerator(seed=42).generate(difficulty="easy")
        engine = GameEngine(track)
        engine.state.race_info.status = RaceStatus.FINISHED

        # Register the session both as a known game session and as a
        # lobby-bound session (the WS module's bookkeeping).
        game_route._game_sessions["session-finish-test"] = engine
        game_route._lobby_sessions.add("session-finish-test")
        try:
            await game_route.broadcast_game_state("session-finish-test")

            # Lobby flipped to FINISHED.
            assert lobby.status == LobbyStatus.FINISHED
            # And a lobby_state broadcast went out exactly once.
            lobby_state_msgs = [
                m for (lid, m) in captured
                if lid == lobby.lobby_id and m["type"] == "lobby_state"
            ]
            assert len(lobby_state_msgs) == 1

            # Idempotency: a second broadcast tick after the transition
            # must NOT re-broadcast (finish_race returns False the
            # second time, so the gate holds).
            captured.clear()
            await game_route.broadcast_game_state("session-finish-test")
            assert captured == []
        finally:
            game_route._game_sessions.pop("session-finish-test", None)
            game_route._lobby_sessions.discard("session-finish-test")

    @pytest.mark.asyncio
    async def test_broadcast_game_state_skips_finish_for_non_lobby_session(self, monkeypatch):
        """Direct-mode (non-lobby) races must not trip the lobby
        propagation path — there's no lobby to update.
        """
        from app.api.routes import game as game_route
        from app.core.engine import GameEngine, RaceStatus
        from app.core.track import TrackGenerator

        captured = []

        async def fake_broadcast(lobby_id, message, exclude_player_id=None):
            captured.append(message)

        monkeypatch.setattr(game_route, "broadcast_to_lobby", fake_broadcast)

        track = TrackGenerator(seed=42).generate(difficulty="easy")
        engine = GameEngine(track)
        engine.state.race_info.status = RaceStatus.FINISHED

        game_route._game_sessions["session-direct"] = engine
        # NOT adding to _lobby_sessions ⇒ this is a direct-mode race.
        try:
            await game_route.broadcast_game_state("session-direct")
            assert captured == []  # no lobby broadcasts
        finally:
            game_route._game_sessions.pop("session-direct", None)

    @pytest.mark.asyncio
    async def test_engine_finish_propagates_without_active_connections(self, monkeypatch):
        """Regression: when the host leaves /race before the race wraps
        up, the engine keeps ticking on the server and transitions to
        FINISHED on its own — but `state_broadcaster` was gating the
        propagation to the lobby behind `manager.active_connections`,
        so the lobby was left pinned at RACING forever. Verify the
        FINISHED transition fires even with zero active connections.
        """
        from app.api.routes import game as game_route
        from app.core.engine import GameEngine, RaceStatus
        from app.core.lobby import LobbyStatus
        from app.core.track import TrackGenerator

        captured = []

        async def fake_broadcast(lobby_id, message, exclude_player_id=None):
            captured.append((lobby_id, message))

        monkeypatch.setattr(game_route, "broadcast_to_lobby", fake_broadcast)

        manager = get_lobby_manager()
        lobby = manager.create_lobby("Race", "host_player")
        lobby.status = LobbyStatus.RACING
        lobby.game_session_id = "session-no-listeners"

        track = TrackGenerator(seed=42).generate(difficulty="easy")
        engine = GameEngine(track)
        engine.state.race_info.status = RaceStatus.FINISHED

        game_route._game_sessions["session-no-listeners"] = engine
        game_route._lobby_sessions.add("session-no-listeners")
        # Crucially: NO entry in manager.active_connections for this
        # session — simulates the host having left the race screen.
        try:
            transitioned = await game_route._propagate_engine_finish_to_lobby(
                "session-no-listeners"
            )
            assert transitioned is True
            assert lobby.status == LobbyStatus.FINISHED
            # Lobby_state broadcast went out to the (now-empty) lobby.
            assert any(
                lid == lobby.lobby_id and m["type"] == "lobby_state"
                for (lid, m) in captured
            )

            # Idempotent on second call.
            captured.clear()
            transitioned2 = await game_route._propagate_engine_finish_to_lobby(
                "session-no-listeners"
            )
            assert transitioned2 is False
            assert captured == []
        finally:
            game_route._game_sessions.pop("session-no-listeners", None)
            game_route._lobby_sessions.discard("session-no-listeners")

    @pytest.mark.asyncio
    async def test_disconnect_with_missing_lobby_does_not_raise(self, monkeypatch):
        """Defensive: a stale lobby_id (already disbanded) must not crash
        the disconnect handler.
        """
        from app.api.routes import game as game_route

        async def fake_broadcast(lobby_id, message, exclude_player_id=None):
            pass

        monkeypatch.setattr(game_route, "broadcast_to_lobby", fake_broadcast)

        # No lobby with this id exists.
        await game_route.handle_leave_lobby("nonexistent", "player_x")


class TestCreateLobby:
    """Test POST /lobbies endpoint."""

    def test_create_lobby_minimal(self, client):
        """Test creating lobby with minimal parameters."""
        response = client.post(
            "/lobbies",
            json={
                "name": "Test Lobby",
                "host_player_id": "player1"
            }
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test Lobby"
        assert data["host_player_id"] == "player1"
        assert data["status"] == "waiting"
        assert len(data["members"]) == 1
        assert data["members"][0]["player_id"] == "player1"
        assert data["members"][0]["ready"] is True  # Host auto-ready
        assert data["settings"]["track_difficulty"] == "medium"
        assert data["settings"]["max_players"] == 8

    def test_create_lobby_with_custom_settings(self, client):
        """Test creating lobby with custom settings."""
        response = client.post(
            "/lobbies",
            json={
                "name": "Hard Lobby",
                "host_player_id": "player1",
                "track_difficulty": "hard",
                "track_seed": 12345,
                "max_players": 4
            }
        )

        assert response.status_code == 201
        data = response.json()
        assert data["settings"]["track_difficulty"] == "hard"
        assert data["settings"]["track_seed"] == 12345
        assert data["settings"]["max_players"] == 4

    def test_create_lobby_invalid_name(self, client):
        """Test creating lobby with invalid name."""
        response = client.post(
            "/lobbies",
            json={
                "name": "",  # Empty name
                "host_player_id": "player1"
            }
        )

        assert response.status_code == 422  # Validation error

    def test_create_lobby_invalid_max_players(self, client):
        """Test creating lobby with invalid max_players."""
        response = client.post(
            "/lobbies",
            json={
                "name": "Test",
                "host_player_id": "player1",
                "max_players": 99  # Too high
            }
        )

        assert response.status_code == 422  # Validation error


class TestListLobbies:
    """Test GET /lobbies endpoint."""

    def test_list_lobbies_empty(self, client):
        """Test listing lobbies when none exist."""
        response = client.get("/lobbies")

        assert response.status_code == 200
        data = response.json()
        assert data == []

    def test_list_lobbies_multiple(self, client):
        """Test listing multiple lobbies."""
        # Create 3 lobbies
        client.post("/lobbies", json={"name": "Lobby 1", "host_player_id": "player1"})
        client.post("/lobbies", json={"name": "Lobby 2", "host_player_id": "player2"})
        client.post("/lobbies", json={"name": "Lobby 3", "host_player_id": "player3"})

        response = client.get("/lobbies")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3

        # Lobbies sorted by created_at (newest first)
        assert data[0]["name"] == "Lobby 3"
        assert data[1]["name"] == "Lobby 2"
        assert data[2]["name"] == "Lobby 1"

    def test_list_lobbies_with_status_filter(self, client):
        """Test listing lobbies filtered by status."""
        # Create lobby
        create_response = client.post(
            "/lobbies",
            json={"name": "Waiting Lobby", "host_player_id": "player1"}
        )
        lobby_id = create_response.json()["lobby_id"]

        # Change status to racing
        manager = get_lobby_manager()
        lobby = manager.get_lobby(lobby_id)
        manager.start_race(lobby_id, "player1")
        manager.transition_to_racing(lobby_id)

        # Create another waiting lobby
        client.post("/lobbies", json={"name": "Lobby 2", "host_player_id": "player2"})

        # Filter by waiting
        response = client.get("/lobbies?status=waiting")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Lobby 2"

        # Filter by racing
        response = client.get("/lobbies?status=racing")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Waiting Lobby"

    def test_list_lobbies_invalid_status_filter(self, client):
        """Test listing lobbies with invalid status filter."""
        response = client.get("/lobbies?status=invalid")

        assert response.status_code == 400
        assert "Invalid status" in response.json()["detail"]

    def test_list_item_format(self, client):
        """Test list item has correct format."""
        client.post("/lobbies", json={"name": "Test", "host_player_id": "player1"})

        response = client.get("/lobbies")
        data = response.json()

        item = data[0]
        assert "lobby_id" in item
        assert "name" in item
        assert "member_count" in item
        assert "max_players" in item
        assert "status" in item
        assert item["member_count"] == 1


class TestGetLobby:
    """Test GET /lobbies/{lobby_id} endpoint."""

    def test_get_lobby_success(self, client):
        """Test getting lobby details."""
        # Create lobby
        create_response = client.post(
            "/lobbies",
            json={"name": "Test Lobby", "host_player_id": "player1"}
        )
        lobby_id = create_response.json()["lobby_id"]

        # Get lobby details
        response = client.get(f"/lobbies/{lobby_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["lobby_id"] == lobby_id
        assert data["name"] == "Test Lobby"
        assert data["host_player_id"] == "player1"
        assert len(data["members"]) == 1

    def test_get_lobby_not_found(self, client):
        """Test getting non-existent lobby."""
        response = client.get("/lobbies/invalid-id")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]


class TestUpdateSettings:
    """Test PUT /lobbies/{lobby_id}/settings endpoint."""

    def test_update_settings_by_host(self, client):
        """Test host updating lobby settings."""
        # Create lobby
        create_response = client.post(
            "/lobbies",
            json={"name": "Test Lobby", "host_player_id": "player1"}
        )
        lobby_id = create_response.json()["lobby_id"]

        # Update settings
        response = client.put(
            f"/lobbies/{lobby_id}/settings?player_id=player1",
            json={
                "track_difficulty": "extreme",
                "track_seed": 99999,
                "max_players": 4
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["settings"]["track_difficulty"] == "extreme"
        assert data["settings"]["track_seed"] == 99999
        assert data["settings"]["max_players"] == 4

    def test_update_settings_partial(self, client):
        """Test partial settings update."""
        # Create lobby
        create_response = client.post(
            "/lobbies",
            json={
                "name": "Test Lobby",
                "host_player_id": "player1",
                "track_difficulty": "medium",
                "max_players": 8
            }
        )
        lobby_id = create_response.json()["lobby_id"]

        # Update only difficulty
        response = client.put(
            f"/lobbies/{lobby_id}/settings?player_id=player1",
            json={"track_difficulty": "hard"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["settings"]["track_difficulty"] == "hard"
        assert data["settings"]["max_players"] == 8  # Unchanged

    def test_update_settings_by_non_host(self, client):
        """Test non-host trying to update settings."""
        # Create lobby
        create_response = client.post(
            "/lobbies",
            json={"name": "Test Lobby", "host_player_id": "player1"}
        )
        lobby_id = create_response.json()["lobby_id"]

        # Try to update as non-host
        response = client.put(
            f"/lobbies/{lobby_id}/settings?player_id=player2",
            json={"track_difficulty": "hard"}
        )

        assert response.status_code == 403
        assert "Only the host" in response.json()["detail"]

    def test_update_settings_wrong_status(self, client):
        """Test updating settings in non-WAITING status."""
        # Create lobby and start race
        create_response = client.post(
            "/lobbies",
            json={"name": "Test Lobby", "host_player_id": "player1"}
        )
        lobby_id = create_response.json()["lobby_id"]

        # Start race
        manager = get_lobby_manager()
        manager.start_race(lobby_id, "player1")

        # Try to update settings
        response = client.put(
            f"/lobbies/{lobby_id}/settings?player_id=player1",
            json={"track_difficulty": "hard"}
        )

        assert response.status_code == 400
        assert "Cannot update settings" in response.json()["detail"]

    def test_update_settings_lobby_not_found(self, client):
        """Test updating settings for non-existent lobby."""
        response = client.put(
            "/lobbies/invalid-id/settings?player_id=player1",
            json={"track_difficulty": "hard"}
        )

        assert response.status_code == 404


class TestDisbandLobby:
    """Test DELETE /lobbies/{lobby_id} endpoint."""

    def test_disband_lobby_by_host(self, client):
        """Test host disbanding lobby."""
        # Create lobby
        create_response = client.post(
            "/lobbies",
            json={"name": "Test Lobby", "host_player_id": "player1"}
        )
        lobby_id = create_response.json()["lobby_id"]

        # Disband lobby
        response = client.delete(f"/lobbies/{lobby_id}?player_id=player1")

        assert response.status_code == 204

        # Verify lobby is gone
        get_response = client.get(f"/lobbies/{lobby_id}")
        assert get_response.status_code == 404

    def test_disband_lobby_by_non_host(self, client):
        """Test non-host trying to disband lobby."""
        # Create lobby
        create_response = client.post(
            "/lobbies",
            json={"name": "Test Lobby", "host_player_id": "player1"}
        )
        lobby_id = create_response.json()["lobby_id"]

        # Try to disband as non-host
        response = client.delete(f"/lobbies/{lobby_id}?player_id=player2")

        assert response.status_code == 403
        # Message updated when disband was opened up to creator-or-host (#169).
        assert "host or creator" in response.json()["detail"]

    def test_disband_lobby_not_found(self, client):
        """Test disbanding non-existent lobby."""
        response = client.delete("/lobbies/invalid-id?player_id=player1")

        assert response.status_code == 404


class TestResetLobby:
    """Test POST /lobbies/{lobby_id}/reset endpoint (powers 'Race Again')."""

    def test_reset_finished_lobby_by_host(self, client):
        """A FINISHED lobby resets back to WAITING and the dropped engine
        session is removed from in-memory bookkeeping.
        """
        from app.api.routes import game as game_route
        from app.core.engine import GameEngine
        from app.core.lobby import LobbyStatus
        from app.core.track import TrackGenerator

        create = client.post(
            "/lobbies",
            json={"name": "L", "host_player_id": "player1"},
        )
        lobby_id = create.json()["lobby_id"]

        # Put the lobby in FINISHED with a dangling engine session, the
        # state the lobby ends up in after a race wraps up.
        manager = get_lobby_manager()
        lobby = manager.get_lobby(lobby_id)
        lobby.status = LobbyStatus.FINISHED
        lobby.game_session_id = "old-session"
        track = TrackGenerator(seed=1).generate(difficulty="easy")
        game_route._game_sessions["old-session"] = GameEngine(track)
        game_route._lobby_sessions.add("old-session")

        try:
            response = client.post(
                f"/lobbies/{lobby_id}/reset?player_id=player1",
            )
            assert response.status_code == 200
            assert response.json()["status"] == "waiting"
            assert response.json()["game_session_id"] is None
            # Orphaned engine cleaned up so it doesn't pile up.
            assert "old-session" not in game_route._game_sessions
            assert "old-session" not in game_route._lobby_sessions
        finally:
            game_route._game_sessions.pop("old-session", None)
            game_route._lobby_sessions.discard("old-session")

    def test_reset_lobby_by_non_host_returns_403(self, client):
        from app.core.lobby import LobbyStatus
        create = client.post(
            "/lobbies",
            json={"name": "L", "host_player_id": "player1"},
        )
        lobby_id = create.json()["lobby_id"]
        manager = get_lobby_manager()
        manager.get_lobby(lobby_id).status = LobbyStatus.FINISHED

        response = client.post(
            f"/lobbies/{lobby_id}/reset?player_id=stranger",
        )
        assert response.status_code == 403

    def test_reset_non_finished_lobby_returns_400(self, client):
        create = client.post(
            "/lobbies",
            json={"name": "L", "host_player_id": "player1"},
        )
        lobby_id = create.json()["lobby_id"]
        # Lobby is still WAITING — can't reset.
        response = client.post(
            f"/lobbies/{lobby_id}/reset?player_id=player1",
        )
        assert response.status_code == 400

    def test_reset_missing_lobby_returns_404(self, client):
        response = client.post(
            "/lobbies/does-not-exist/reset?player_id=player1",
        )
        assert response.status_code == 404


class TestListLobbiesIncludesFinished:
    """The lobby browser also fetches FINISHED lobbies so the host can
    'Race Again' on a lobby they previously raced in.
    """

    def test_status_finished_filter_returns_finished_lobbies(self, client):
        from app.core.lobby import LobbyStatus
        create = client.post(
            "/lobbies",
            json={"name": "L", "host_player_id": "player1"},
        )
        lobby_id = create.json()["lobby_id"]
        get_lobby_manager().get_lobby(lobby_id).status = LobbyStatus.FINISHED

        response = client.get("/lobbies?status=finished")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["lobby_id"] == lobby_id
        assert data[0]["status"] == "finished"


class TestEndToEndWorkflow:
    """Test complete lobby workflow via REST API."""

    def test_lobby_lifecycle(self, client):
        """Test complete lobby lifecycle."""
        # 1. Create lobby
        create_response = client.post(
            "/lobbies",
            json={
                "name": "Integration Test Lobby",
                "host_player_id": "player1",
                "track_difficulty": "medium",
                "max_players": 4
            }
        )
        assert create_response.status_code == 201
        lobby_id = create_response.json()["lobby_id"]

        # 2. List lobbies
        list_response = client.get("/lobbies")
        assert list_response.status_code == 200
        assert len(list_response.json()) == 1

        # 3. Get lobby details
        get_response = client.get(f"/lobbies/{lobby_id}")
        assert get_response.status_code == 200
        assert get_response.json()["name"] == "Integration Test Lobby"

        # 4. Update settings
        update_response = client.put(
            f"/lobbies/{lobby_id}/settings?player_id=player1",
            json={"track_difficulty": "hard"}
        )
        assert update_response.status_code == 200
        assert update_response.json()["settings"]["track_difficulty"] == "hard"

        # 5. Verify update persisted
        get_response2 = client.get(f"/lobbies/{lobby_id}")
        assert get_response2.json()["settings"]["track_difficulty"] == "hard"

        # 6. Disband lobby
        disband_response = client.delete(f"/lobbies/{lobby_id}?player_id=player1")
        assert disband_response.status_code == 204

        # 7. Verify lobby gone
        final_list = client.get("/lobbies")
        assert len(final_list.json()) == 0
