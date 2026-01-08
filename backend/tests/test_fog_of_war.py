"""
Tests for fog of war / opponent visibility system (#117).

Verifies that bots only see opponents within configured visibility range.
"""

import pytest
import math
from app.core.engine import GameEngine, RaceStatus
from app.core.physics import Vector2
from app.core.track import TrackGenerator
from app.config import get_settings


@pytest.fixture
def settings():
    """Get game settings."""
    return get_settings()


@pytest.fixture
def test_track():
    """Generate a simple test track."""
    generator = TrackGenerator(seed=42)
    return generator.generate(difficulty='easy')


@pytest.fixture
def engine(test_track):
    """Create a game engine with a test track."""
    return GameEngine(test_track)


def create_stationary_bot_code():
    """Bot code that doesn't move - used for testing static positioning."""
    return """
class TestBot(BaseBot):
    def on_tick(self, state):
        # Store opponent data in memory for inspection
        self.memory['opponent_count'] = len(state.opponents)
        self.memory['opponents'] = [
            {
                'distance': opp.distance,
                'relative_angle': opp.relative_angle,
                'position': opp.position
            }
            for opp in state.opponents
        ]
        return BotActions()  # No movement
"""


class TestOpponentVisibility:
    """Test fog of war filtering for opponent data."""

    def test_opponent_within_range_is_visible(self, engine, settings):
        """Test that opponent within visibility range is visible."""
        # Create two bots
        bot_code = create_stationary_bot_code()
        player1 = engine.add_bot_player("bot1", bot_code, "TestBot")
        player2 = engine.add_bot_player("bot2", bot_code, "TestBot")

        # Start race (must start before positioning to avoid reset)
        engine.start_race()
        engine.state.race_info.status = RaceStatus.RACING
        engine.state.race_info.start_time = 0.0

        # Position them 100 units apart (well within 300 unit range)
        player1.car.position = Vector2(0, 0)
        player2.car.position = Vector2(100, 0)

        # Run 3 ticks to execute bot at 20Hz
        for _ in range(3):
            engine._tick()

        # Bot1 should see Bot2
        assert 'opponent_count' in player1.bot_instance.memory
        assert player1.bot_instance.memory['opponent_count'] == 1

        # Check distance is correct
        opponents = player1.bot_instance.memory['opponents']
        assert len(opponents) == 1
        assert pytest.approx(opponents[0]['distance'], rel=0.01) == 100.0

    def test_opponent_beyond_range_is_hidden(self, engine, settings):
        """Test that opponent beyond visibility range is hidden."""
        # Create two bots
        bot_code = create_stationary_bot_code()
        player1 = engine.add_bot_player("bot1", bot_code, "TestBot")
        player2 = engine.add_bot_player("bot2", bot_code, "TestBot")

        # Start race
        engine.start_race()
        engine.state.race_info.status = RaceStatus.RACING
        engine.state.race_info.start_time = 0.0

        # Position them 400 units apart (beyond 300 unit range)
        player1.car.position = Vector2(0, 0)
        player2.car.position = Vector2(400, 0)

        # Run 3 ticks to execute bot
        for _ in range(3):
            engine._tick()

        # Bot1 should NOT see Bot2
        assert 'opponent_count' in player1.bot_instance.memory
        assert player1.bot_instance.memory['opponent_count'] == 0

    def test_opponent_exactly_at_boundary(self, engine, settings):
        """Test opponent exactly at visibility boundary is visible."""
        # Create two bots
        bot_code = create_stationary_bot_code()
        player1 = engine.add_bot_player("bot1", bot_code, "TestBot")
        player2 = engine.add_bot_player("bot2", bot_code, "TestBot")

        # Start race
        engine.start_race()
        engine.state.race_info.status = RaceStatus.RACING
        engine.state.race_info.start_time = 0.0

        # Position them exactly 300 units apart
        visibility_radius = settings.bot.OPPONENT_VISIBILITY_RADIUS
        player1.car.position = Vector2(0, 0)
        player2.car.position = Vector2(visibility_radius, 0)

        # Run 3 ticks
        for _ in range(3):
            engine._tick()

        # Bot1 should see Bot2 (boundary is inclusive: distance <= radius)
        assert player1.bot_instance.memory['opponent_count'] == 1
        opponents = player1.bot_instance.memory['opponents']
        assert pytest.approx(opponents[0]['distance'], rel=0.01) == visibility_radius

    def test_multiple_opponents_mixed_visibility(self, engine, settings):
        """Test with multiple opponents at various distances."""
        bot_code = create_stationary_bot_code()
        player1 = engine.add_bot_player("bot1", bot_code, "TestBot")
        player2 = engine.add_bot_player("bot2", bot_code, "TestBot")
        player3 = engine.add_bot_player("bot3", bot_code, "TestBot")
        player4 = engine.add_bot_player("bot4", bot_code, "TestBot")
        player5 = engine.add_bot_player("bot5", bot_code, "TestBot")

        # Start race
        engine.start_race()
        engine.state.race_info.status = RaceStatus.RACING
        engine.state.race_info.start_time = 0.0

        # Position: bot1 at origin, others at various distances
        player1.car.position = Vector2(0, 0)
        player2.car.position = Vector2(100, 0)    # 100 units - visible
        player3.car.position = Vector2(0, 250)    # 250 units - visible
        player4.car.position = Vector2(350, 0)    # 350 units - hidden
        player5.car.position = Vector2(0, 500)    # 500 units - hidden

        # Run 3 ticks
        for _ in range(3):
            engine._tick()

        # Bot1 should see only 2 opponents (bot2 and bot3)
        assert player1.bot_instance.memory['opponent_count'] == 2

        # Verify distances
        opponents = player1.bot_instance.memory['opponents']
        distances = sorted([opp['distance'] for opp in opponents])
        assert pytest.approx(distances[0], rel=0.01) == 100.0
        assert pytest.approx(distances[1], rel=0.01) == 250.0

    def test_distance_calculation_accuracy(self, engine, settings):
        """Test that distance calculation is accurate (Euclidean)."""
        bot_code = create_stationary_bot_code()
        player1 = engine.add_bot_player("bot1", bot_code, "TestBot")
        player2 = engine.add_bot_player("bot2", bot_code, "TestBot")

        # Start race
        engine.start_race()
        engine.state.race_info.status = RaceStatus.RACING
        engine.state.race_info.start_time = 0.0

        # Position at (0,0) and (30,40) - should give distance 50
        # Using larger values so car movement during ticks is negligible
        player1.car.position = Vector2(0, 0)
        player1.car.velocity = Vector2(0, 0)
        player2.car.position = Vector2(30, 40)
        player2.car.velocity = Vector2(0, 0)

        # Run 3 ticks
        for _ in range(3):
            engine._tick()

        # Check distance = sqrt(30^2 + 40^2) = 50
        opponents = player1.bot_instance.memory['opponents']
        assert len(opponents) == 1
        assert pytest.approx(opponents[0]['distance'], rel=0.02) == 50.0

    def test_relative_angle_calculation(self, engine, settings):
        """Test relative angle calculation for various opponent positions."""
        bot_code = create_stationary_bot_code()
        player1 = engine.add_bot_player("bot1", bot_code, "TestBot")
        player2 = engine.add_bot_player("bot2", bot_code, "TestBot")

        # Start race once
        engine.start_race()
        engine.state.race_info.status = RaceStatus.RACING
        engine.state.race_info.start_time = 0.0

        # Test cases: opponent at different angles
        test_cases = [
            # (opponent_pos, expected_relative_angle, check_abs)
            (Vector2(100, 0), 0.0, False),              # Directly ahead (east)
            (Vector2(0, 100), math.pi / 2, False),      # Left (north)
            (Vector2(-100, 0), math.pi, True),          # Behind (west) - can be ±π
            (Vector2(0, -100), -math.pi / 2, False),    # Right (south)
        ]

        for opponent_pos, expected_angle, check_abs in test_cases:
            # Bot1 at origin, facing east (heading = 0)
            player1.car.position = Vector2(0, 0)
            player1.car.heading = 0.0
            player1.car.velocity = Vector2(0, 0)
            player2.car.position = opponent_pos
            player2.car.velocity = Vector2(0, 0)

            # Run 3 ticks
            for _ in range(3):
                engine._tick()

            # Check relative angle
            opponents = player1.bot_instance.memory['opponents']
            assert len(opponents) == 1
            actual_angle = opponents[0]['relative_angle']

            if check_abs:
                # For directly behind, accept either π or -π
                assert pytest.approx(abs(actual_angle), abs=0.01) == abs(expected_angle)
            else:
                assert pytest.approx(actual_angle, abs=0.01) == expected_angle

    def test_relative_angle_normalization(self, engine, settings):
        """Test that relative angles are normalized to [-π, π]."""
        bot_code = create_stationary_bot_code()
        player1 = engine.add_bot_player("bot1", bot_code, "TestBot")
        player2 = engine.add_bot_player("bot2", bot_code, "TestBot")

        # Start race
        engine.start_race()
        engine.state.race_info.status = RaceStatus.RACING
        engine.state.race_info.start_time = 0.0

        # Bot1 facing west (heading = π), opponent to the east
        player1.car.position = Vector2(0, 0)
        player1.car.heading = math.pi  # Facing west
        player2.car.position = Vector2(100, 0)  # East of bot1

        # Run 3 ticks
        for _ in range(3):
            engine._tick()

        # Opponent is behind bot (should be π, not -π)
        opponents = player1.bot_instance.memory['opponents']
        assert len(opponents) == 1
        angle = opponents[0]['relative_angle']

        # Check angle is normalized to [-π, π]
        assert -math.pi <= angle <= math.pi
        # In this case, should be π (directly behind)
        assert pytest.approx(abs(angle), abs=0.01) == math.pi

    def test_opponent_data_fields(self, engine, settings):
        """Test that BotOpponent only exposes safe fields."""
        bot_code = """
class TestBot(BaseBot):
    def on_tick(self, state):
        if state.opponents:
            opp = state.opponents[0]
            # Store available fields
            self.memory['has_position'] = hasattr(opp, 'position')
            self.memory['has_velocity'] = hasattr(opp, 'velocity')
            self.memory['has_heading'] = hasattr(opp, 'heading')
            self.memory['has_distance'] = hasattr(opp, 'distance')
            self.memory['has_relative_angle'] = hasattr(opp, 'relative_angle')
            # These should NOT be available
            self.memory['has_bot_code'] = hasattr(opp, 'bot_code')
            self.memory['has_memory'] = hasattr(opp, 'memory')
            self.memory['has_bot_instance'] = hasattr(opp, 'bot_instance')
        return BotActions()
"""
        player1 = engine.add_bot_player("bot1", bot_code, "TestBot")
        player2 = engine.add_bot_player("bot2", bot_code, "TestBot")

        # Start race
        engine.start_race()
        engine.state.race_info.status = RaceStatus.RACING
        engine.state.race_info.start_time = 0.0

        # Position close together
        player1.car.position = Vector2(0, 0)
        player2.car.position = Vector2(50, 0)

        # Run 3 ticks
        for _ in range(3):
            engine._tick()

        # Check safe fields are available
        assert player1.bot_instance.memory['has_position'] is True
        assert player1.bot_instance.memory['has_velocity'] is True
        assert player1.bot_instance.memory['has_heading'] is True
        assert player1.bot_instance.memory['has_distance'] is True
        assert player1.bot_instance.memory['has_relative_angle'] is True

        # Check unsafe fields are NOT available
        assert player1.bot_instance.memory['has_bot_code'] is False
        assert player1.bot_instance.memory['has_memory'] is False
        assert player1.bot_instance.memory['has_bot_instance'] is False

    def test_self_excluded_from_opponents(self, engine, settings):
        """Test that bot does not appear in its own opponents list."""
        bot_code = create_stationary_bot_code()
        player1 = engine.add_bot_player("bot1", bot_code, "TestBot")

        # Start race
        engine.start_race()
        engine.state.race_info.status = RaceStatus.RACING
        engine.state.race_info.start_time = 0.0

        # Only one bot - should see no opponents
        player1.car.position = Vector2(0, 0)

        # Run 3 ticks
        for _ in range(3):
            engine._tick()

        # Should see 0 opponents (not itself)
        assert player1.bot_instance.memory['opponent_count'] == 0

    def test_fog_of_war_with_bot_race(self, engine, settings):
        """Integration test: Full bot race with dynamic visibility."""
        # Bot that moves forward
        bot_code = """
class TestBot(BaseBot):
    def on_tick(self, state):
        self.memory['opponent_count'] = len(state.opponents)
        return BotActions(accelerate=True)
"""
        player1 = engine.add_bot_player("bot1", bot_code, "TestBot")
        player2 = engine.add_bot_player("bot2", bot_code, "TestBot")
        player3 = engine.add_bot_player("bot3", bot_code, "TestBot")

        # Start race
        engine.start_race()
        engine.state.race_info.status = RaceStatus.RACING
        engine.state.race_info.start_time = 0.0

        # Start close together
        player1.car.position = Vector2(0, 0)
        player2.car.position = Vector2(50, 0)
        player3.car.position = Vector2(400, 0)  # Far away

        # Run initial ticks
        for _ in range(3):
            engine._tick()

        # Bot1 should see bot2 but not bot3
        assert player1.bot_instance.memory['opponent_count'] == 1

        # Now move bot3 closer
        player3.car.position = Vector2(100, 0)

        # Run more ticks
        for _ in range(3):
            engine._tick()

        # Now bot1 should see both bot2 and bot3
        assert player1.bot_instance.memory['opponent_count'] == 2
