"""
Regression tests for newly implemented features.

Tests cover:
- Checkpoint tracking and split times (#107)
- Race position ranking (#108)
- Nitro boost system (#110)
"""

import pytest
from app.core.engine import GameEngine, RaceStatus
from app.core.physics import CarState, Vector2, CarPhysics
from app.core.track import TrackGenerator
from app.config import get_settings


@pytest.fixture
def settings():
    """Get game settings."""
    return get_settings()


@pytest.fixture
def physics():
    """Create physics engine."""
    return CarPhysics()


@pytest.fixture
def test_track():
    """Generate a test track."""
    generator = TrackGenerator(seed=42)
    return generator.generate(difficulty='easy')


@pytest.fixture
def engine(test_track):
    """Create a game engine with a test track."""
    return GameEngine(test_track)


class TestSplitTimes:
    """Test split times tracking (#107)."""

    def test_player_has_split_times_list(self, engine):
        """Test that players have split_times list initialized."""
        player_id = "test_player"
        engine.add_player(player_id)

        player = engine.state.players[player_id]
        assert hasattr(player, 'split_times')
        assert isinstance(player.split_times, list)
        assert len(player.split_times) == 0

    def test_split_times_reset_on_start_race(self, engine):
        """Test that split times are reset when race starts."""
        player_id = "test_player"
        engine.add_player(player_id)

        player = engine.state.players[player_id]
        # Manually add a split time
        player.split_times.append(10.0)

        # Start race
        engine.start_race()

        # Should be cleared
        assert len(player.split_times) == 0

    def test_split_times_in_snapshot(self, engine):
        """Test that split times are included in state snapshot."""
        player_id = "test_player"
        engine.add_player(player_id)

        player = engine.state.players[player_id]
        player.split_times.append(5.0)
        player.split_times.append(10.5)

        snapshot = engine.get_state_snapshot()
        assert 'split_times' in snapshot['players'][player_id]
        assert snapshot['players'][player_id]['split_times'] == [5.0, 10.5]


class TestPositionRanking:
    """Test real-time race position ranking (#108)."""

    def test_calculate_player_progress(self, engine):
        """Test progress calculation method exists."""
        player_id = "test_player"
        engine.add_player(player_id)

        player = engine.state.players[player_id]
        progress = engine._calculate_player_progress(player)

        # Should return a numeric value
        # Progress can be negative if player is far from first checkpoint
        assert isinstance(progress, (int, float))
        assert progress != float('inf')  # Should not be infinite unless finished

    def test_progress_increases_with_checkpoints(self, engine):
        """Test that progress increases when checkpoints are completed."""
        player_id = "test_player"
        engine.add_player(player_id)

        player = engine.state.players[player_id]

        # Initial progress
        progress_0 = engine._calculate_player_progress(player)

        # Complete a checkpoint
        player.current_checkpoint = 1
        progress_1 = engine._calculate_player_progress(player)

        # Progress should increase
        assert progress_1 > progress_0

    def test_finished_player_has_infinite_progress(self, engine):
        """Test that finished players have infinite progress."""
        player_id = "test_player"
        engine.add_player(player_id)

        player = engine.state.players[player_id]
        player.is_finished = True

        progress = engine._calculate_player_progress(player)
        assert progress == float('inf')

    def test_update_race_positions_assigns_position(self, engine):
        """Test that _update_race_positions assigns positions."""
        player_id = "test_player"
        engine.add_player(player_id)
        engine.start_race()

        # Force racing status
        engine.state.race_info.status = RaceStatus.RACING

        engine._update_race_positions()

        player = engine.state.players[player_id]
        assert player.position == 1

    def test_multiple_players_ranked_correctly(self, engine):
        """Test that multiple players are ranked by progress."""
        player1_id = "player1"
        player2_id = "player2"

        engine.add_player(player1_id)
        engine.add_player(player2_id)
        engine.start_race()

        player1 = engine.state.players[player1_id]
        player2 = engine.state.players[player2_id]

        # Make player1 ahead
        player1.current_checkpoint = 2
        player2.current_checkpoint = 1

        engine.state.race_info.status = RaceStatus.RACING
        engine._update_race_positions()

        assert player1.position == 1
        assert player2.position == 2

    def test_position_in_snapshot(self, engine):
        """Test that position is included in state snapshot."""
        player_id = "test_player"
        engine.add_player(player_id)

        player = engine.state.players[player_id]
        player.position = 3

        snapshot = engine.get_state_snapshot()
        assert snapshot['players'][player_id]['position'] == 3


class TestNitroBoost:
    """Test nitro boost system (#110)."""

    def test_nitro_state_in_car(self, engine, settings):
        """Test that cars have nitro state fields."""
        player_id = "test_player"
        engine.add_player(player_id)

        car = engine.state.players[player_id].car
        assert hasattr(car, 'nitro_charges')
        assert hasattr(car, 'nitro_active')
        assert hasattr(car, 'nitro_remaining_ticks')
        assert car.nitro_charges == settings.car.DEFAULT_NITRO_CHARGES

    def test_nitro_reset_on_start_race(self, engine, settings):
        """Test that nitro is reset when race starts."""
        player_id = "test_player"
        engine.add_player(player_id)

        player = engine.state.players[player_id]
        # Use nitro
        player.car.nitro_charges = 0
        player.car.nitro_active = True

        # Start race
        engine.start_race()

        # Should be reset
        assert player.car.nitro_charges == settings.car.DEFAULT_NITRO_CHARGES
        assert not player.car.nitro_active
        assert player.car.nitro_remaining_ticks == 0

    def test_update_nitro_method_exists(self, physics):
        """Test that update_nitro method exists."""
        car = CarState(
            position=Vector2(0, 0),
            velocity=Vector2(0, 0),
            heading=0,
            nitro_charges=2,
            nitro_active=False,
            nitro_remaining_ticks=0
        )

        # Should not raise
        new_car = physics.update_nitro(car, use_nitro=False)
        assert isinstance(new_car, CarState)

    def test_nitro_activates_when_used(self, physics, settings):
        """Test that nitro activates when use_nitro is True."""
        car = CarState(
            position=Vector2(0, 0),
            velocity=Vector2(50, 0),
            heading=0,
            nitro_charges=2,
            nitro_active=False,
            nitro_remaining_ticks=0
        )

        new_car = physics.update_nitro(car, use_nitro=True)

        assert new_car.nitro_active
        assert new_car.nitro_charges == 1
        # Nitro activates and immediately consumes first tick
        assert new_car.nitro_remaining_ticks == settings.car.DEFAULT_NITRO_DURATION_TICKS - 1

    def test_nitro_depletes_over_time(self, physics):
        """Test that nitro depletes over time."""
        car = CarState(
            position=Vector2(0, 0),
            velocity=Vector2(50, 0),
            heading=0,
            nitro_charges=1,
            nitro_active=True,
            nitro_remaining_ticks=10
        )

        new_car = physics.update_nitro(car, use_nitro=False)

        assert new_car.nitro_active
        assert new_car.nitro_remaining_ticks == 9

    def test_nitro_deactivates_when_depleted(self, physics):
        """Test that nitro deactivates when ticks reach zero."""
        car = CarState(
            position=Vector2(0, 0),
            velocity=Vector2(50, 0),
            heading=0,
            nitro_charges=1,
            nitro_active=True,
            nitro_remaining_ticks=1
        )

        new_car = physics.update_nitro(car, use_nitro=False)

        assert not new_car.nitro_active
        assert new_car.nitro_remaining_ticks == 0

    def test_nitro_cannot_activate_without_charges(self, physics):
        """Test that nitro cannot activate without charges."""
        car = CarState(
            position=Vector2(0, 0),
            velocity=Vector2(50, 0),
            heading=0,
            nitro_charges=0,
            nitro_active=False,
            nitro_remaining_ticks=0
        )

        new_car = physics.update_nitro(car, use_nitro=True)

        assert not new_car.nitro_active
        assert new_car.nitro_charges == 0

    def test_nitro_in_snapshot(self, engine):
        """Test that nitro state is included in state snapshot."""
        player_id = "test_player"
        engine.add_player(player_id)

        player = engine.state.players[player_id]
        player.car.nitro_charges = 1
        player.car.nitro_active = True
        player.car.nitro_remaining_ticks = 60

        snapshot = engine.get_state_snapshot()
        car_snapshot = snapshot['players'][player_id]['car']

        assert car_snapshot['nitro_charges'] == 1
        assert car_snapshot['nitro_active'] == True
        assert car_snapshot['nitro_remaining_ticks'] == 60


class TestRaceLifecycle:
    """Test race state transitions."""

    def test_race_starts_in_waiting(self, engine):
        """Test that race starts in WAITING state."""
        assert engine.state.race_info.status == RaceStatus.WAITING

    def test_start_race_sets_countdown(self, engine):
        """Test that start_race sets COUNTDOWN status."""
        engine.add_player("test_player")
        engine.start_race()

        assert engine.state.race_info.status == RaceStatus.COUNTDOWN
        assert engine.state.race_info.countdown_remaining > 0
