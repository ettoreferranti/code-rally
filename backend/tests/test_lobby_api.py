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
        assert "Only the host" in response.json()["detail"]

    def test_disband_lobby_not_found(self, client):
        """Test disbanding non-existent lobby."""
        response = client.delete("/lobbies/invalid-id?player_id=player1")

        assert response.status_code == 404


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
