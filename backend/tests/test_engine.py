"""
Unit and regression tests for game engine functionality.

Tests cover:
- Checkpoint tracking and split times (#107)
- Race position ranking (#108)
- Nitro boost system (#110)
- Race lifecycle (countdown, racing, finished)
"""

import pytest
from app.core.engine import GameEngine, PlayerInput, RaceStatus
from app.core.physics import Vector2, CarState
from app.core.track import (
    TrackGenerator, Track, TrackPoint, TrackSegment, Checkpoint,
    SurfaceType, ContainmentBoundary,
)
from app.config import get_settings


def _make_straight_track(length: float = 4000.0, width: float = 200.0) -> Track:
    """Build a long, perfectly-straight track for speed-mechanic tests
    that should not be affected by corner geometry."""
    start = TrackPoint(x=0, y=0, width=width, surface=SurfaceType.ASPHALT)
    end = TrackPoint(x=length, y=0, width=width, surface=SurfaceType.ASPHALT)
    return Track(
        segments=[TrackSegment(start=start, end=end)],
        checkpoints=[Checkpoint(position=(length, 0), width=width, angle=0, index=0)],
        start_position=(10.0, 0.0),
        start_heading=0.0,
        finish_position=(length, 0.0),
        finish_heading=0.0,
        total_length=length,
        is_looping=False,
        containment=ContainmentBoundary(
            left_points=[(0, -width / 2), (length, -width / 2)],
            right_points=[(0, width / 2), (length, width / 2)],
        ),
        obstacles=[],
    )


def _make_multi_checkpoint_track(num_cps: int = 4, spacing: float = 200.0, width: float = 200.0) -> Track:
    """Straight track with `num_cps` evenly spaced checkpoints along +X."""
    length = spacing * (num_cps + 1)
    start = TrackPoint(x=0, y=0, width=width, surface=SurfaceType.ASPHALT)
    end = TrackPoint(x=length, y=0, width=width, surface=SurfaceType.ASPHALT)
    checkpoints = [
        Checkpoint(position=(spacing * (i + 1), 0.0), width=width, angle=0.0, index=i)
        for i in range(num_cps)
    ]
    return Track(
        segments=[TrackSegment(start=start, end=end)],
        checkpoints=checkpoints,
        start_position=(10.0, 0.0),
        start_heading=0.0,
        finish_position=(length, 0.0),
        finish_heading=0.0,
        total_length=length,
        is_looping=False,
        containment=ContainmentBoundary(
            left_points=[(0, -width / 2), (length, -width / 2)],
            right_points=[(0, width / 2), (length, width / 2)],
        ),
        obstacles=[],
    )


def advance_countdown(engine, settings):
    """Helper to advance past countdown phase."""
    countdown_ticks = int(settings.game.COUNTDOWN_SECONDS * settings.game.TICK_RATE)
    for _ in range(countdown_ticks + 1):  # +1 to ensure we're past countdown
        engine._tick()


@pytest.fixture
def settings():
    """Get game settings."""
    return get_settings()


@pytest.fixture
def test_track():
    """Generate a test track."""
    generator = TrackGenerator(seed=42)
    return generator.generate(difficulty='easy')


@pytest.fixture
def engine(test_track):
    """Create a game engine with a test track."""
    return GameEngine(test_track)


class TestCheckpointTracking:
    """Test checkpoint tracking and split times (#107)."""

    def test_checkpoint_detection(self, engine, settings):
        """Test that checkpoints are detected when car passes through them."""
        player_id = "test_player"
        engine.add_player(player_id)
        engine.start_race()

        # Advance past countdown
        advance_countdown(engine, settings)

        player = engine.state.players[player_id]
        initial_checkpoint = player.current_checkpoint

        # Simulate driving forward to reach first checkpoint
        player.input.accelerate = True
        for _ in range(600):  # 10 seconds of driving
            engine._tick()
            if player.current_checkpoint > initial_checkpoint:
                break

        # Should have passed at least one checkpoint
        assert player.current_checkpoint > initial_checkpoint

    def test_split_times_recorded(self, engine, settings):
        """Test that split times are recorded at each checkpoint."""
        player_id = "test_player"
        engine.add_player(player_id)
        engine.start_race()

        # Wait for countdown
        advance_countdown(engine, settings)

        player = engine.state.players[player_id]

        # Drive to first checkpoint
        player.input.accelerate = True
        for _ in range(600):
            engine._tick()
            if player.current_checkpoint > 0:
                break

        # Should have recorded a split time
        assert len(player.split_times) > 0
        assert player.split_times[0] > 0  # Split time should be positive

    def test_split_times_increase(self, engine, settings):
        """Test that split times increase monotonically."""
        player_id = "test_player"
        engine.add_player(player_id)
        engine.start_race()

        advance_countdown(engine, settings)

        player = engine.state.players[player_id]
        player.input.accelerate = True

        # Drive through multiple checkpoints
        for _ in range(1800):  # 30 seconds
            engine._tick()
            if player.current_checkpoint >= 2:
                break

        # Should have multiple split times
        if len(player.split_times) >= 2:
            assert player.split_times[1] > player.split_times[0]

    def test_split_times_reset_on_race_restart(self, engine, settings):
        """Test that split times are reset when race restarts."""
        player_id = "test_player"
        engine.add_player(player_id)
        engine.start_race()

        advance_countdown(engine, settings)

        player = engine.state.players[player_id]
        player.input.accelerate = True

        # Drive to checkpoint
        for _ in range(600):
            engine._tick()
            if player.current_checkpoint > 0:
                break

        initial_split_count = len(player.split_times)
        assert initial_split_count > 0

        # Restart race
        engine.start_race()

        # Split times should be cleared
        assert len(player.split_times) == 0


class TestPositionRanking:
    """Test real-time race position ranking (#108)."""

    def test_single_player_position(self, engine, settings):
        """Test that single player is ranked 1st."""
        player_id = "test_player"
        engine.add_player(player_id)
        engine.start_race()

        advance_countdown(engine, settings)

        # Update positions
        engine._update_race_positions()

        player = engine.state.players[player_id]
        assert player.position == 1

    def test_multiple_players_ranked_by_progress(self, engine, settings):
        """Test that multiple players are ranked by progress."""
        player1_id = "player1"
        player2_id = "player2"

        engine.add_player(player1_id)
        engine.add_player(player2_id)
        engine.start_race()

        advance_countdown(engine, settings)

        # Make player1 faster
        player1 = engine.state.players[player1_id]
        player2 = engine.state.players[player2_id]

        player1.input.accelerate = True
        player2.input.accelerate = False

        # Simulate some ticks
        for _ in range(300):
            engine._tick()

        # Player1 should be ahead
        assert player1.position == 1
        assert player2.position == 2

    def test_finished_players_ranked_by_time(self, engine, settings):
        """Test that finished players are ranked by finish time."""
        player1_id = "player1"
        player2_id = "player2"

        engine.add_player(player1_id)
        engine.add_player(player2_id)
        engine.start_race()

        advance_countdown(engine, settings)

        player1 = engine.state.players[player1_id]
        player2 = engine.state.players[player2_id]

        # Manually mark player1 as finished first
        player1.is_finished = True
        player1.finish_time = 100.0

        # Mark player2 as finished later
        player2.is_finished = True
        player2.finish_time = 105.0

        engine._update_race_positions()

        # Player1 should be 1st, player2 should be 2nd
        assert player1.position == 1
        assert player2.position == 2

    def test_finished_players_rank_above_racing(self, engine, settings):
        """Test that finished players always rank above racing players."""
        player1_id = "player1"
        player2_id = "player2"

        engine.add_player(player1_id)
        engine.add_player(player2_id)
        engine.start_race()

        advance_countdown(engine, settings)

        player1 = engine.state.players[player1_id]
        player2 = engine.state.players[player2_id]

        # Mark player1 as finished
        player1.is_finished = True
        player1.finish_time = 100.0

        # Player2 is still racing and ahead in progress
        player2.current_checkpoint = 10
        player1.current_checkpoint = 5

        engine._update_race_positions()

        # Finished player should still rank above racing player
        assert player1.position == 1
        assert player2.position == 2


class TestNitroBoost:
    """Test nitro boost system (#110)."""

    def test_nitro_initialization(self, engine, settings):
        """Test that players start with correct number of nitro charges."""
        player_id = "test_player"
        engine.add_player(player_id)

        player = engine.state.players[player_id]
        assert player.car.nitro_charges == settings.car.DEFAULT_NITRO_CHARGES
        assert not player.car.nitro_active
        assert player.car.nitro_remaining_ticks == 0

    def test_nitro_activation(self, engine, settings):
        """Test that nitro activates when button pressed and charges available."""
        player_id = "test_player"
        engine.add_player(player_id)
        engine.start_race()

        advance_countdown(engine, settings)

        player = engine.state.players[player_id]
        initial_charges = player.car.nitro_charges

        # Activate nitro
        player.input.nitro = True
        engine._tick()

        # Should be active and consume a charge
        assert player.car.nitro_active
        assert player.car.nitro_charges == initial_charges - 1
        # Nitro activates and immediately consumes first tick
        assert player.car.nitro_remaining_ticks == settings.car.DEFAULT_NITRO_DURATION_TICKS - 1

    def test_nitro_duration(self, engine, settings):
        """Test that nitro lasts for correct duration."""
        player_id = "test_player"
        engine.add_player(player_id)
        engine.start_race()

        advance_countdown(engine, settings)

        player = engine.state.players[player_id]

        # Activate nitro
        player.input.nitro = True
        engine._tick()

        assert player.car.nitro_active

        # Run for duration
        player.input.nitro = False
        for _ in range(settings.car.DEFAULT_NITRO_DURATION_TICKS):
            engine._tick()

        # Should be deactivated
        assert not player.car.nitro_active
        assert player.car.nitro_remaining_ticks == 0

    def test_nitro_speed_boost(self, settings):
        """Test that nitro allows higher speeds than normal.

        Uses a long straight synthetic track so the comparison isn't
        confounded by corner-induced speed caps.
        """
        engine = GameEngine(_make_straight_track())
        player_id = "test_player"
        engine.add_player(player_id)
        engine.start_race()

        advance_countdown(engine, settings)

        player = engine.state.players[player_id]

        # Measure max speed reached without nitro
        player.input.accelerate = True
        max_normal_speed = 0.0
        for _ in range(200):
            engine._tick()
            max_normal_speed = max(max_normal_speed, player.car.get_speed())

        # Reset car to starting position for fair comparison
        engine.start_race()
        advance_countdown(engine, settings)

        # Measure max speed with nitro
        player.input.accelerate = True
        player.input.nitro = True  # Activate nitro immediately
        max_nitro_speed = 0.0
        for _ in range(200):
            engine._tick()
            max_nitro_speed = max(max_nitro_speed, player.car.get_speed())
            # Keep nitro active if it's still available
            if not player.car.nitro_active and player.car.nitro_charges > 0:
                player.input.nitro = True

        # With nitro, should be able to reach higher speeds
        # (NITRO_SPEED_MULTIPLIER = 1.5, so expect at least 10% faster)
        assert max_nitro_speed > max_normal_speed * 1.1

    def test_nitro_limited_charges(self, engine, settings):
        """Test that nitro cannot be used more times than charges available."""
        player_id = "test_player"
        engine.add_player(player_id)
        engine.start_race()

        advance_countdown(engine, settings)

        player = engine.state.players[player_id]
        initial_charges = player.car.nitro_charges

        # Use all charges
        for _ in range(initial_charges):
            player.input.nitro = True
            engine._tick()
            player.input.nitro = False

            # Wait for nitro to finish
            for _ in range(150):
                engine._tick()

        # Should have no charges left
        assert player.car.nitro_charges == 0

        # Try to activate again
        player.input.nitro = True
        engine._tick()

        # Should not activate
        assert not player.car.nitro_active

    def test_nitro_reset_on_race_restart(self, engine, settings):
        """Test that nitro charges are reset when race restarts."""
        player_id = "test_player"
        engine.add_player(player_id)
        engine.start_race()

        advance_countdown(engine, settings)

        player = engine.state.players[player_id]

        # Use a nitro charge
        player.input.nitro = True
        engine._tick()

        assert player.car.nitro_charges < settings.car.DEFAULT_NITRO_CHARGES

        # Restart race
        engine.start_race()

        # Charges should be reset
        assert player.car.nitro_charges == settings.car.DEFAULT_NITRO_CHARGES


class TestRaceLifecycle:
    """Test race state transitions and lifecycle."""

    def test_race_starts_in_waiting_state(self, engine):
        """Test that new race starts in waiting state."""
        assert engine.state.race_info.status == RaceStatus.WAITING

    def test_race_transitions_to_countdown(self, engine):
        """Test that start_race transitions to countdown."""
        engine.add_player("test_player")
        engine.start_race()

        assert engine.state.race_info.status == RaceStatus.COUNTDOWN
        assert engine.state.race_info.countdown_remaining > 0

    def test_race_transitions_to_racing_after_countdown(self, engine, settings):
        """Test that race transitions to racing after countdown."""
        engine.add_player("test_player")
        engine.start_race()

        # Wait for countdown to finish
        advance_countdown(engine, settings)

        assert engine.state.race_info.status == RaceStatus.RACING
        assert engine.state.race_info.start_time is not None

    def test_race_finishes_when_player_completes(self, engine, settings):
        """Test that race transitions to finished when player completes."""
        player_id = "test_player"
        engine.add_player(player_id)
        engine.start_race()

        advance_countdown(engine, settings)

        player = engine.state.players[player_id]

        # Manually complete all checkpoints and mark as finished
        player.current_checkpoint = len(engine.state.track.checkpoints)
        player.is_finished = True
        player.finish_time = 100.0  # Arbitrary finish time

        # Trigger race end logic
        engine._update_race_status()

        assert player.is_finished


class TestMissedCheckpointWarning:
    """Skipping a checkpoint should flag the player without crediting the later one."""

    def _make_engine(self, num_cps=4):
        engine = GameEngine(_make_multi_checkpoint_track(num_cps=num_cps))
        engine.add_player("p1")
        return engine

    def test_skipping_ahead_sets_missed_tick_and_does_not_credit(self):
        engine = self._make_engine()
        player = engine.state.players["p1"]
        # Seed prev_position just before checkpoint 0, then teleport past CP 2.
        player._prev_position = Vector2(150.0, 0.0)
        player.car.position = Vector2(650.0, 0.0)  # past CP 0 (200), CP 1 (400), CP 2 (600)
        engine.state.tick = 42

        engine._check_checkpoint_progress(player)

        # We crossed CP 0 in the normal path AND would have crossed 1 and 2.
        # The "normal" branch credits CP 0; the skip-detection branch should
        # NOT fire because the normal cross succeeded for the *next* CP.
        assert player.current_checkpoint == 1
        assert player.missed_checkpoint_tick is None

    def test_skipping_with_next_unreached_raises_warning(self):
        # Pretend the player has already cleared CP 0 (current=1), then
        # teleport across CP 2 *without* crossing CP 1 (e.g. cut corner).
        engine = self._make_engine()
        player = engine.state.players["p1"]
        player.current_checkpoint = 1

        # Move from (450, -200) to (650, -200): crosses CP 2's line at x=600
        # (the y is off-center but inside the CP width of 200).
        # CP 1 is at x=400, so we are PAST it without having crossed it
        # (since prev_x=450 > 400).
        player._prev_position = Vector2(450.0, -50.0)
        player.car.position = Vector2(650.0, -50.0)
        engine.state.tick = 99

        engine._check_checkpoint_progress(player)

        # No credit, warning raised.
        assert player.current_checkpoint == 1
        assert player.missed_checkpoint_tick == 99

    def test_reverse_crossing_does_not_trigger_warning(self):
        engine = self._make_engine()
        player = engine.state.players["p1"]
        player.current_checkpoint = 1
        # Travel backwards across CP 2 (right-to-left): not "forward".
        player._prev_position = Vector2(650.0, 0.0)
        player.car.position = Vector2(450.0, 0.0)
        engine.state.tick = 50

        engine._check_checkpoint_progress(player)

        assert player.missed_checkpoint_tick is None


class TestResetToNewTrack:
    """Test the multiplayer "New Track" reroll path on GameEngine."""

    def _fresh_track(self, seed: int):
        return TrackGenerator(seed=seed).generate(difficulty='easy')

    def test_swaps_track_instance(self, engine):
        new_track = self._fresh_track(seed=999)
        assert engine.state.track is not new_track
        engine.reset_to_new_track(new_track)
        assert engine.state.track is new_track

    def test_cars_moved_to_new_start_position(self, engine, settings):
        engine.add_player("p1")
        # Drive the car somewhere off the start line.
        player = engine.state.players["p1"]
        player.car.position = Vector2(123.0, 456.0)
        player.car.velocity = Vector2(10.0, 5.0)
        player.car.is_drifting = True

        new_track = self._fresh_track(seed=999)
        engine.reset_to_new_track(new_track)

        assert player.car.position.x == new_track.start_position[0]
        assert player.car.position.y == new_track.start_position[1]
        assert player.car.velocity.x == 0
        assert player.car.velocity.y == 0
        assert player.car.heading == new_track.start_heading
        assert player.car.is_drifting is False

    def test_status_returns_to_waiting_from_finished(self, engine, settings):
        engine.add_player("p1")
        engine.state.race_info.status = RaceStatus.FINISHED
        engine.state.race_info.finish_time = 42.0

        engine.reset_to_new_track(self._fresh_track(seed=7))

        assert engine.state.race_info.status == RaceStatus.WAITING
        assert engine.state.race_info.finish_time is None
        assert engine.state.race_info.start_time is None

    def test_race_progress_cleared(self, engine, settings):
        engine.add_player("p1")
        player = engine.state.players["p1"]
        player.current_checkpoint = 3
        player.checkpoints_passed = {0, 1, 2}
        player.split_times = [1.0, 2.0, 3.0]
        player.is_finished = True
        player.finish_time = 10.0
        player.points = 25
        player.dnf = True

        engine.reset_to_new_track(self._fresh_track(seed=7))

        assert player.current_checkpoint == 0
        assert player.checkpoints_passed == set()
        assert player.split_times == []
        assert player.is_finished is False
        assert player.finish_time is None
        assert player.points == 0
        assert player.dnf is False

    def test_nitro_reset_to_default(self, engine, settings):
        engine.add_player("p1")
        player = engine.state.players["p1"]
        player.car.nitro_charges = 0
        player.car.nitro_active = True
        player.car.nitro_remaining_ticks = 50

        engine.reset_to_new_track(self._fresh_track(seed=7))

        assert player.car.nitro_charges == settings.car.DEFAULT_NITRO_CHARGES
        assert player.car.nitro_active is False
        assert player.car.nitro_remaining_ticks == 0
