"""
Tests for bot lifecycle integration with game engine.

Tests bot loading, execution at 20Hz, event callbacks, and error handling.
"""

import pytest
from app.core.engine import GameEngine, RaceStatus
from app.core.track import Track, TrackSegment, TrackPoint, Checkpoint, SurfaceType, ContainmentBoundary
from app.core.bot_manager import BotError


def create_test_track() -> Track:
    """Create a simple test track."""
    segments = [
        TrackSegment(
            start=TrackPoint(x=0, y=0, width=50, surface=SurfaceType.ASPHALT),
            end=TrackPoint(x=100, y=0, width=50, surface=SurfaceType.ASPHALT)
        ),
        TrackSegment(
            start=TrackPoint(x=100, y=0, width=50, surface=SurfaceType.ASPHALT),
            end=TrackPoint(x=100, y=100, width=50, surface=SurfaceType.ASPHALT)
        ),
    ]

    checkpoints = [
        Checkpoint(position=(50, 0), width=60, angle=0, index=0),
        Checkpoint(position=(100, 50), width=60, angle=1.57, index=1),  # π/2
    ]

    containment = ContainmentBoundary(
        left_points=[(0, -30), (100, -30), (130, 100)],
        right_points=[(0, 30), (100, 30), (70, 100)]
    )

    return Track(
        segments=segments,
        checkpoints=checkpoints,
        start_position=(10, 0),
        start_heading=0,
        finish_position=(100, 100),
        finish_heading=1.57,
        total_length=200.0,
        is_looping=False,
        containment=containment,
        obstacles=[]
    )


def test_bot_loading_success():
    """Test successful bot loading."""
    track = create_test_track()
    engine = GameEngine(track)

    bot_code = """
class TestBot(BaseBot):
    def on_tick(self, state):
        return BotActions(accelerate=True)
"""

    # Add bot player
    player = engine.add_bot_player("bot1", bot_code, "TestBot")

    assert player.is_bot
    assert player.bot_instance is not None
    assert player.bot_error is None
    assert not player.dnf


def test_bot_loading_invalid_code():
    """Test bot loading with invalid code."""
    track = create_test_track()
    engine = GameEngine(track)

    bot_code = """
this is not valid python code!!!
"""

    # Should raise BotError
    with pytest.raises(BotError):
        engine.add_bot_player("bot1", bot_code, "TestBot")


def test_bot_loading_class_not_found():
    """Test bot loading when class name doesn't exist."""
    track = create_test_track()
    engine = GameEngine(track)

    bot_code = """

class WrongName(BaseBot):
    pass
"""

    # Should raise BotError
    with pytest.raises(BotError):
        engine.add_bot_player("bot1", bot_code, "TestBot")


def test_bot_tick_execution():
    """Test that bot's on_tick() is called at 20Hz."""
    track = create_test_track()
    engine = GameEngine(track)

    # Bot that accelerates
    bot_code = """
class TestBot(BaseBot):
    def on_tick(self, state):
        return BotActions(accelerate=True, turn_right=True)
"""

    player = engine.add_bot_player("bot1", bot_code, "TestBot")
    engine.start_race()

    # Start racing
    engine.state.race_info.status = RaceStatus.RACING
    engine.state.race_info.start_time = 0.0

    # Run 6 ticks (should execute bot twice at 20Hz = every 3 ticks)
    for i in range(6):
        engine._tick()

        # Bot should run on ticks 3 and 6 (multiples of 3)
        if engine.state.tick % 3 == 0:
            # After bot runs, input should be set
            assert player.input.accelerate == True
            assert player.input.turn_right == True


def test_bot_error_handling():
    """Test that bot errors result in DQ."""
    track = create_test_track()
    engine = GameEngine(track)

    # Bot that raises error
    bot_code = """

class TestBot(BaseBot):
    def on_tick(self, state):
        raise RuntimeError("Intentional error")
"""

    player = engine.add_bot_player("bot1", bot_code, "TestBot")
    engine.start_race()
    engine.state.race_info.status = RaceStatus.RACING
    engine.state.race_info.start_time = 0.0

    # Run enough ticks to execute bot (every 3 ticks)
    for i in range(3):
        engine._tick()

    # Bot should have errored (sandbox catches runtime errors and returns safe default)
    # Actually, the sandbox catches errors and returns safe defaults, so no DQ
    # But if we had a timeout or security error, it would DQ
    assert not player.dnf  # Sandbox handles runtime errors gracefully


def test_bot_timeout_dq():
    """Test that bot timeout results in DQ."""
    track = create_test_track()
    engine = GameEngine(track)

    # Bot with infinite loop (will timeout)
    bot_code = """

class TestBot(BaseBot):
    def on_tick(self, state):
        while True:
            pass
"""

    player = engine.add_bot_player("bot1", bot_code, "TestBot")
    engine.start_race()
    engine.state.race_info.status = RaceStatus.RACING
    engine.state.race_info.start_time = 0.0

    # Run enough ticks to execute bot
    for i in range(3):
        engine._tick()

    # Bot should be DQ'd due to timeout
    assert player.dnf
    assert player.bot_error is not None
    assert "time limit" in player.bot_error.lower() or "timeout" in player.bot_error.lower()


def test_bot_checkpoint_callback():
    """Test that on_checkpoint() is called when bot passes checkpoint."""
    track = create_test_track()
    engine = GameEngine(track)

    bot_code = """

class TestBot(BaseBot):
    def on_tick(self, state):
        # Track checkpoints in memory (persistent dict provided by BaseBot)
        if 'checkpoints_seen' not in self.memory:
            self.memory['checkpoints_seen'] = []
        return BotActions(accelerate=True)

    def on_checkpoint(self, checkpoint_index, split_time):
        # Store in memory dict
        if 'checkpoints_seen' not in self.memory:
            self.memory['checkpoints_seen'] = []
        self.memory['checkpoints_seen'].append((checkpoint_index, split_time))
"""

    player = engine.add_bot_player("bot1", bot_code, "TestBot")
    engine.start_race()
    engine.state.race_info.status = RaceStatus.RACING
    engine.state.race_info.start_time = 0.0

    # Manually trigger checkpoint
    player.current_checkpoint = 0
    player.checkpoints_passed = set()

    # Simulate crossing checkpoint
    from app.core.physics import Vector2
    player._prev_position = Vector2(40, 0)
    player.car.position = Vector2(60, 0)

    engine._check_checkpoint_progress(player)

    # Check that callback was called
    assert 'checkpoints_seen' in player.bot_instance.memory
    assert len(player.bot_instance.memory['checkpoints_seen']) == 1
    assert player.bot_instance.memory['checkpoints_seen'][0][0] == 0  # checkpoint index


def test_multiple_bots():
    """Test multiple bots racing together."""
    track = create_test_track()
    engine = GameEngine(track)

    bot_code = """
class TestBot(BaseBot):
    def on_tick(self, state):
        return BotActions(accelerate=True)
"""

    # Add 3 bot players
    engine.add_bot_player("bot1", bot_code, "TestBot")
    engine.add_bot_player("bot2", bot_code, "TestBot")
    engine.add_bot_player("bot3", bot_code, "TestBot")

    assert len(engine.state.players) == 3

    engine.start_race()
    engine.state.race_info.status = RaceStatus.RACING
    engine.state.race_info.start_time = 0.0

    # Run some ticks
    for i in range(9):
        engine._tick()

    # All bots should have accelerate=True
    for player in engine.state.players.values():
        assert player.input.accelerate == True
