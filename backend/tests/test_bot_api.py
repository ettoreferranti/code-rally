"""
Unit tests for bot API type definitions.

Tests ensure that the bot API types are correctly defined and provide
all necessary data for bot development.
"""

import pytest
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


class TestBotCarState:
    """Test bot car state data structure."""

    def test_create_bot_car_state(self):
        """Test creating a BotCarState instance."""
        car = BotCarState(
            position=(100.0, 200.0),
            heading=1.5708,  # 90 degrees
            speed=50.0,
            velocity=(0.0, 50.0),
            angular_velocity=0.0,
            health=100.0,
            nitro_charges=2,
            nitro_active=False,
            current_surface="asphalt",
            off_track=False
        )

        assert car.position == (100.0, 200.0)
        assert car.heading == 1.5708
        assert car.speed == 50.0
        assert car.velocity == (0.0, 50.0)
        assert car.nitro_charges == 2
        assert not car.nitro_active
        assert car.current_surface == "asphalt"
        assert not car.off_track

    def test_bot_car_state_immutable(self):
        """Test that BotCarState is frozen (immutable)."""
        car = BotCarState(
            position=(0.0, 0.0),
            heading=0.0,
            speed=0.0,
            velocity=(0.0, 0.0),
            angular_velocity=0.0,
            health=100.0,
            nitro_charges=2,
            nitro_active=False,
            current_surface="asphalt",
            off_track=False
        )

        with pytest.raises(Exception):  # FrozenInstanceError
            car.speed = 100.0


class TestBotRaycast:
    """Test bot raycast sensor data."""

    def test_create_raycast(self):
        """Test creating a raycast result."""
        ray = BotRaycast(
            distance=150.0,
            hit_type="boundary"
        )

        assert ray.distance == 150.0
        assert ray.hit_type == "boundary"

    def test_raycast_no_hit(self):
        """Test raycast with no obstacle hit."""
        ray = BotRaycast(
            distance=200.0,  # Max distance
            hit_type=None
        )

        assert ray.distance == 200.0
        assert ray.hit_type is None


class TestBotTrackState:
    """Test bot track state data."""

    def test_create_track_state(self):
        """Test creating track state."""
        checkpoints = [(100, 200), (300, 400), (500, 600)]
        track = BotTrackState(
            checkpoints=checkpoints,
            next_checkpoint=1,
            distance_to_boundary_left=50.0,
            distance_to_boundary_right=45.0,
            upcoming_surface="gravel",
            upcoming_turn="left",
            turn_sharpness=0.7
        )

        assert track.checkpoints == checkpoints
        assert track.next_checkpoint == 1
        assert track.distance_to_boundary_left == 50.0
        assert track.distance_to_boundary_right == 45.0
        assert track.upcoming_surface == "gravel"
        assert track.upcoming_turn == "left"
        assert track.turn_sharpness == 0.7


class TestBotOpponent:
    """Test bot opponent data."""

    def test_create_opponent(self):
        """Test creating opponent data."""
        opponent = BotOpponent(
            position=(200.0, 300.0),
            velocity=(30.0, 40.0),
            heading=0.785,  # 45 degrees
            distance=100.0,
            relative_angle=0.5
        )

        assert opponent.position == (200.0, 300.0)
        assert opponent.velocity == (30.0, 40.0)
        assert opponent.heading == 0.785
        assert opponent.distance == 100.0
        assert opponent.relative_angle == 0.5


class TestBotRaceState:
    """Test bot race state data."""

    def test_create_race_state(self):
        """Test creating race state."""
        race = BotRaceState(
            current_checkpoint=3,
            total_checkpoints=10,
            position=2,
            total_cars=5,
            elapsed_time=45.5,
            distance_to_finish=500.0
        )

        assert race.current_checkpoint == 3
        assert race.total_checkpoints == 10
        assert race.position == 2
        assert race.total_cars == 5
        assert race.elapsed_time == 45.5
        assert race.distance_to_finish == 500.0


class TestBotGameState:
    """Test complete bot game state."""

    def test_create_game_state(self):
        """Test creating complete game state for bot."""
        car = BotCarState(
            position=(100.0, 200.0),
            heading=0.0,
            speed=50.0,
            velocity=(50.0, 0.0),
            angular_velocity=0.0,
            health=100.0,
            nitro_charges=2,
            nitro_active=False,
            current_surface="asphalt",
            off_track=False
        )

        track = BotTrackState(
            checkpoints=[(100, 200), (300, 400)],
            next_checkpoint=0,
            distance_to_boundary_left=50.0,
            distance_to_boundary_right=50.0,
            upcoming_surface="asphalt",
            upcoming_turn="straight",
            turn_sharpness=0.0
        )

        rays = [
            BotRaycast(distance=200.0, hit_type=None) for _ in range(7)
        ]

        race = BotRaceState(
            current_checkpoint=0,
            total_checkpoints=2,
            position=1,
            total_cars=1,
            elapsed_time=0.0,
            distance_to_finish=1000.0
        )

        state = BotGameState(
            car=car,
            track=track,
            rays=rays,
            opponents=[],
            race=race
        )

        assert state.car.position == (100.0, 200.0)
        assert len(state.rays) == 7
        assert state.race.total_checkpoints == 2
        assert len(state.opponents) == 0

    def test_game_state_with_opponents(self):
        """Test game state includes opponent data."""
        car = BotCarState(
            position=(0.0, 0.0), heading=0.0, speed=0.0, velocity=(0.0, 0.0),
            angular_velocity=0.0, health=100.0, nitro_charges=2,
            nitro_active=False, current_surface="asphalt", off_track=False
        )

        track = BotTrackState(
            checkpoints=[], next_checkpoint=0,
            distance_to_boundary_left=50.0, distance_to_boundary_right=50.0,
            upcoming_surface="asphalt", upcoming_turn="straight", turn_sharpness=0.0
        )

        opponent1 = BotOpponent(
            position=(100.0, 0.0), velocity=(0.0, 0.0),
            heading=0.0, distance=100.0, relative_angle=0.0
        )

        opponent2 = BotOpponent(
            position=(-50.0, 50.0), velocity=(0.0, 0.0),
            heading=0.0, distance=70.7, relative_angle=2.36
        )

        race = BotRaceState(
            current_checkpoint=0, total_checkpoints=5, position=1,
            total_cars=3, elapsed_time=10.0, distance_to_finish=800.0
        )

        state = BotGameState(
            car=car, track=track, rays=[BotRaycast(200.0, None)] * 7,
            opponents=[opponent1, opponent2], race=race
        )

        assert len(state.opponents) == 2
        assert state.opponents[0].distance == 100.0
        assert state.opponents[1].distance == 70.7


class TestBotActions:
    """Test bot action data structure."""

    def test_create_default_actions(self):
        """Test creating default (no input) actions."""
        actions = BotActions()

        assert not actions.accelerate
        assert not actions.brake
        assert not actions.turn_left
        assert not actions.turn_right
        assert not actions.use_nitro

    def test_create_custom_actions(self):
        """Test creating custom actions."""
        actions = BotActions(
            accelerate=True,
            brake=False,
            turn_left=False,
            turn_right=True,
            use_nitro=False
        )

        assert actions.accelerate
        assert not actions.brake
        assert not actions.turn_left
        assert actions.turn_right
        assert not actions.use_nitro

    def test_actions_to_dict(self):
        """Test converting actions to dictionary."""
        actions = BotActions(
            accelerate=True,
            turn_right=True
        )

        action_dict = actions.to_dict()

        assert action_dict == {
            "accelerate": True,
            "brake": False,
            "turn_left": False,
            "turn_right": True,
            "use_nitro": False
        }

    def test_actions_from_dict(self):
        """Test creating actions from dictionary."""
        action_dict = {
            "accelerate": True,
            "brake": False,
            "turn_left": True,
            "turn_right": False,
            "use_nitro": False
        }

        actions = BotActions.from_dict(action_dict)

        assert actions.accelerate
        assert not actions.brake
        assert actions.turn_left
        assert not actions.turn_right
        assert not actions.use_nitro


class TestCollisionEvent:
    """Test collision event data."""

    def test_create_boundary_collision(self):
        """Test creating a boundary collision event."""
        event = CollisionEvent(
            other_type="boundary",
            impact_speed=50.0,
            direction=1.57,  # 90 degrees
            other_id=None
        )

        assert event.other_type == "boundary"
        assert event.impact_speed == 50.0
        assert event.direction == 1.57
        assert event.other_id is None

    def test_create_car_collision(self):
        """Test creating a car collision event."""
        event = CollisionEvent(
            other_type="car",
            impact_speed=30.0,
            direction=-0.785,  # -45 degrees
            other_id="player_123"
        )

        assert event.other_type == "car"
        assert event.impact_speed == 30.0
        assert event.direction == -0.785
        assert event.other_id == "player_123"

    def test_create_obstacle_collision(self):
        """Test creating an obstacle collision event."""
        event = CollisionEvent(
            other_type="obstacle",
            impact_speed=70.0,
            direction=0.0,
            other_id=None
        )

        assert event.other_type == "obstacle"
        assert event.impact_speed == 70.0
        assert event.direction == 0.0
        assert event.other_id is None
