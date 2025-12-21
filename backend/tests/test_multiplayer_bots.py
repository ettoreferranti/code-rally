"""
Regression tests for multiplayer bot movement.

Tests for bug fixes related to bots not moving in multiplayer races.
"""

import pytest
from app.core.engine import GameEngine, RaceStatus
from app.core.physics import Vector2
from app.core.track import Track, TrackPoint, TrackSegment, Checkpoint, SurfaceType, ContainmentBoundary


def create_test_track() -> Track:
    """Create a simple test track for regression tests."""
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
        Checkpoint(position=(100, 50), width=60, angle=1.57, index=1),
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


def test_bot_actions_converted_to_dict():
    """
    Regression test: Bot actions must be converted from BotActions to dict.

    Bug: Bots returned BotActions objects, but sandbox expected dicts,
    causing all actions to be False.

    Fix: Added to_dict() conversion in sandbox.py
    """
    track = create_test_track()
    engine = GameEngine(track)

    # Simple bot that accelerates
    bot_code = """
class TestBot(BaseBot):
    def on_tick(self, state):
        return BotActions(accelerate=True)
"""

    player = engine.add_bot_player("bot1", bot_code, "TestBot")
    engine.start_race()
    engine.state.race_info.status = RaceStatus.RACING
    engine.state.race_info.start_time = 0.0

    # Run several ticks
    initial_speed = player.car.velocity.magnitude()
    for i in range(10):
        engine._tick()

    # Bot should have accelerated
    final_speed = player.car.velocity.magnitude()
    assert final_speed > initial_speed, "Bot should have accelerated (BotActions converted to dict)"


def test_bot_can_access_array_elements():
    """
    Regression test: Bots must be able to access array elements like state.rays[0].

    Bug: RestrictedPython blocked array access because _getitem_ guard was missing.

    Fix: Added _getitem_ guard to sandbox globals
    """
    track = create_test_track()
    engine = GameEngine(track)

    # Bot that uses array access
    bot_code = """
class TestBot(BaseBot):
    def on_tick(self, state):
        # Access first ray (requires _getitem_ guard)
        front_ray = state.rays[0]

        # Make a decision based on it
        if front_ray.distance < 100:
            return BotActions(brake=True)
        return BotActions(accelerate=True)
"""

    player = engine.add_bot_player("bot1", bot_code, "TestBot")
    engine.start_race()
    engine.state.race_info.status = RaceStatus.RACING
    engine.state.race_info.start_time = 0.0

    # Run several ticks - bot should not error
    for i in range(10):
        engine._tick()

    # Bot should not be DQ'd
    assert not player.dnf, "Bot should not be DQ'd (array access works)"
    assert player.bot_error is None, "Bot should have no errors"


def test_bot_globals_available_without_imports():
    """
    Regression test: BaseBot and BotActions must be available without imports.

    Bug: Bot code tried to import BaseBot/BotActions but imports were blocked.

    Fix: BaseBot and BotActions are added to sandbox globals
    """
    track = create_test_track()
    engine = GameEngine(track)

    # Bot that doesn't import anything (uses globals)
    bot_code = """
class TestBot(BaseBot):
    def on_tick(self, state):
        # Both BaseBot and BotActions available as globals
        return BotActions(accelerate=True, turn_left=True)
"""

    player = engine.add_bot_player("bot1", bot_code, "TestBot")
    engine.start_race()
    engine.state.race_info.status = RaceStatus.RACING
    engine.state.race_info.start_time = 0.0

    # Run several ticks
    for i in range(6):
        engine._tick()

    # Bot should have set input correctly
    if engine.state.tick % 3 == 0:  # Bot runs at 20Hz (every 3 ticks)
        assert player.input.accelerate == True, "Bot should have set accelerate"
        assert player.input.turn_left == True, "Bot should have set turn_left"


def test_multiple_bots_move_in_multiplayer():
    """
    Integration test: Multiple bots should move independently in multiplayer.

    This is the end-to-end scenario that was failing.
    """
    track = create_test_track()
    engine = GameEngine(track)

    # Bot 1: Always accelerates
    bot1_code = """
class Bot1(BaseBot):
    def on_tick(self, state):
        return BotActions(accelerate=True)
"""

    # Bot 2: Accelerates and turns right
    bot2_code = """
class Bot2(BaseBot):
    def on_tick(self, state):
        return BotActions(accelerate=True, turn_right=True)
"""

    bot1 = engine.add_bot_player("bot1", bot1_code, "Bot1")
    bot2 = engine.add_bot_player("bot2", bot2_code, "Bot2")

    engine.start_race()
    engine.state.race_info.status = RaceStatus.RACING
    engine.state.race_info.start_time = 0.0

    # Run simulation
    initial_bot1_speed = bot1.car.velocity.magnitude()
    initial_bot2_speed = bot2.car.velocity.magnitude()
    initial_bot2_heading = bot2.car.heading

    for i in range(30):
        engine._tick()

    # Both bots should have moved
    assert bot1.car.velocity.magnitude() > initial_bot1_speed, "Bot1 should have accelerated"
    assert bot2.car.velocity.magnitude() > initial_bot2_speed, "Bot2 should have accelerated"

    # Bot2 should have turned (heading changed)
    assert bot2.car.heading != initial_bot2_heading, "Bot2 should have turned right"
