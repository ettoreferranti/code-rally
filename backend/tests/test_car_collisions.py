"""
Tests for car-to-car collision detection and response.

Tests circle-based collision detection, elastic collision physics,
and momentum transfer based on car weights.
"""

import pytest
import math
from app.core.engine import GameEngine, RaceStatus
from app.core.physics import Vector2, create_car_at_position
from app.core.track import Track, TrackSegment, TrackPoint, Checkpoint, SurfaceType, ContainmentBoundary


def create_test_track() -> Track:
    """Create a simple wide track for collision testing."""
    segments = [
        TrackSegment(
            start=TrackPoint(x=0, y=0, width=200, surface=SurfaceType.ASPHALT),
            end=TrackPoint(x=500, y=0, width=200, surface=SurfaceType.ASPHALT)
        ),
    ]

    checkpoints = [
        Checkpoint(position=(250, 0), width=250, angle=0, index=0),
    ]

    containment = ContainmentBoundary(
        left_points=[(0, -150), (500, -150)],
        right_points=[(0, 150), (500, 150)]
    )

    return Track(
        segments=segments,
        checkpoints=checkpoints,
        start_position=(10, 0),
        start_heading=0,
        finish_position=(490, 0),
        finish_heading=0,
        total_length=500.0,
        is_looping=False,
        containment=containment,
        obstacles=[]
    )


def test_car_collision_detection():
    """Test that cars colliding are detected."""
    track = create_test_track()
    engine = GameEngine(track)

    # Add two players
    player1 = engine.add_player("player1")
    player2 = engine.add_player("player2")

    engine.start_race()
    engine.state.race_info.status = RaceStatus.RACING
    engine.state.race_info.start_time = 0.0

    # Position cars 15 units apart (collision distance is 20 units = 2 * radius)
    player1.car.position = Vector2(100, 0)
    player2.car.position = Vector2(115, 0)

    # Give them velocities toward each other
    player1.car.velocity = Vector2(50, 0)  # Moving right
    player2.car.velocity = Vector2(-50, 0)  # Moving left

    # Run collision detection
    engine._handle_car_collisions()

    # Check that velocities were modified (collision occurred)
    # After elastic collision, cars should bounce back
    assert player1.car.velocity.x < 50  # Player 1 slowed down
    assert player2.car.velocity.x > -50  # Player 2 slowed down (less negative)


def test_no_collision_when_far_apart():
    """Test that cars far apart don't collide."""
    track = create_test_track()
    engine = GameEngine(track)

    player1 = engine.add_player("player1")
    player2 = engine.add_player("player2")

    engine.start_race()
    engine.state.race_info.status = RaceStatus.RACING
    engine.state.race_info.start_time = 0.0

    # Position cars 100 units apart
    player1.car.position = Vector2(100, 0)
    player2.car.position = Vector2(200, 0)

    # Give them velocities
    player1.car.velocity = Vector2(50, 0)
    player2.car.velocity = Vector2(50, 0)

    initial_v1 = player1.car.velocity.x
    initial_v2 = player2.car.velocity.x

    # Run collision detection
    engine._handle_car_collisions()

    # Velocities should be unchanged
    assert player1.car.velocity.x == initial_v1
    assert player2.car.velocity.x == initial_v2


def test_collision_separation():
    """Test that overlapping cars are pushed apart."""
    track = create_test_track()
    engine = GameEngine(track)

    player1 = engine.add_player("player1")
    player2 = engine.add_player("player2")

    engine.start_race()
    engine.state.race_info.status = RaceStatus.RACING
    engine.state.race_info.start_time = 0.0

    # Position cars overlapping (10 units apart, should be 20)
    player1.car.position = Vector2(100, 0)
    player2.car.position = Vector2(110, 0)

    # Run collision detection
    engine._handle_car_collisions()

    # Calculate new distance
    dx = player2.car.position.x - player1.car.position.x
    dy = player2.car.position.y - player1.car.position.y
    distance = (dx * dx + dy * dy) ** 0.5

    # Cars should be pushed apart to at least collision distance (20 units)
    assert distance >= 19.9  # Allow small floating point error


def test_weight_affects_collision():
    """Test that heavier cars push lighter cars more."""
    track = create_test_track()
    engine = GameEngine(track)

    # Light car (weight 30) vs heavy car (weight 90)
    light = engine.add_player("light")
    heavy = engine.add_player("heavy")

    light.weight = 30.0
    heavy.weight = 90.0

    engine.start_race()
    engine.state.race_info.status = RaceStatus.RACING
    engine.state.race_info.start_time = 0.0

    # Position cars close together
    light.car.position = Vector2(100, 0)
    heavy.car.position = Vector2(115, 0)

    # Give them equal velocities toward each other
    light.car.velocity = Vector2(50, 0)
    heavy.car.velocity = Vector2(-50, 0)

    initial_light_pos = light.car.position.x
    initial_heavy_pos = heavy.car.position.x

    # Run collision detection
    engine._handle_car_collisions()

    # Calculate how much each car moved
    light_displacement = abs(light.car.position.x - initial_light_pos)
    heavy_displacement = abs(heavy.car.position.x - initial_heavy_pos)

    # Light car should be pushed more than heavy car
    assert light_displacement > heavy_displacement


def test_elastic_collision_momentum():
    """Test that momentum is conserved in elastic collision."""
    track = create_test_track()
    engine = GameEngine(track)

    player1 = engine.add_player("player1")
    player2 = engine.add_player("player2")

    # Equal weights
    player1.weight = 60.0
    player2.weight = 60.0

    engine.start_race()
    engine.state.race_info.status = RaceStatus.RACING
    engine.state.race_info.start_time = 0.0

    # Position cars close together
    player1.car.position = Vector2(100, 0)
    player2.car.position = Vector2(115, 0)

    # Player 1 moving fast, player 2 stationary
    player1.car.velocity = Vector2(100, 0)
    player2.car.velocity = Vector2(0, 0)

    # Calculate initial momentum
    initial_momentum_x = (player1.weight * player1.car.velocity.x +
                          player2.weight * player2.car.velocity.x)

    # Run collision detection
    engine._handle_car_collisions()

    # Calculate final momentum
    final_momentum_x = (player1.weight * player1.car.velocity.x +
                        player2.weight * player2.car.velocity.x)

    # Momentum should be approximately conserved (within floating point error)
    assert abs(initial_momentum_x - final_momentum_x) < 1.0

    # After collision, player 1 should slow down and player 2 should speed up
    assert player1.car.velocity.x < 100
    assert player2.car.velocity.x > 0


def test_collision_only_when_moving_together():
    """Test that collision only occurs when cars are moving toward each other."""
    track = create_test_track()
    engine = GameEngine(track)

    player1 = engine.add_player("player1")
    player2 = engine.add_player("player2")

    engine.start_race()
    engine.state.race_info.status = RaceStatus.RACING
    engine.state.race_info.start_time = 0.0

    # Position cars close together
    player1.car.position = Vector2(100, 0)
    player2.car.position = Vector2(115, 0)

    # Both moving in same direction
    player1.car.velocity = Vector2(50, 0)
    player2.car.velocity = Vector2(50, 0)

    initial_v1_x = player1.car.velocity.x
    initial_v2_x = player2.car.velocity.x

    # Run collision detection
    engine._handle_car_collisions()

    # Cars should be separated but velocities unchanged (no collision response)
    # since they're not moving toward each other
    # Note: Velocities might change slightly, but should be similar
    assert abs(player1.car.velocity.x - initial_v1_x) < 10
    assert abs(player2.car.velocity.x - initial_v2_x) < 10


def test_multiple_car_collisions():
    """Test collision handling with 3+ cars."""
    track = create_test_track()
    engine = GameEngine(track)

    car1 = engine.add_player("car1")
    car2 = engine.add_player("car2")
    car3 = engine.add_player("car3")

    engine.start_race()
    engine.state.race_info.status = RaceStatus.RACING
    engine.state.race_info.start_time = 0.0

    # Position cars in a line with some close together
    car1.car.position = Vector2(100, 0)
    car2.car.position = Vector2(115, 0)  # Close to car1
    car3.car.position = Vector2(200, 0)  # Far from others

    car1.car.velocity = Vector2(50, 0)
    car2.car.velocity = Vector2(-50, 0)
    car3.car.velocity = Vector2(0, 0)

    initial_car3_velocity = car3.car.velocity.x

    # Run collision detection
    engine._handle_car_collisions()

    # Car 1 and 2 should have collided
    assert car1.car.velocity.x != 50 or car2.car.velocity.x != -50

    # Car 3 should be unaffected
    assert car3.car.velocity.x == initial_car3_velocity


def test_finished_cars_dont_collide():
    """Test that finished cars don't participate in collisions."""
    track = create_test_track()
    engine = GameEngine(track)

    player1 = engine.add_player("player1")
    player2 = engine.add_player("player2")

    engine.start_race()
    engine.state.race_info.status = RaceStatus.RACING
    engine.state.race_info.start_time = 0.0

    # Position cars close together
    player1.car.position = Vector2(100, 0)
    player2.car.position = Vector2(115, 0)

    # Mark player 2 as finished
    player2.is_finished = True

    player1.car.velocity = Vector2(50, 0)
    player2.car.velocity = Vector2(-50, 0)

    initial_v1 = player1.car.velocity.x
    initial_v2 = player2.car.velocity.x

    # Run collision detection
    engine._handle_car_collisions()

    # Velocities should be unchanged (no collision with finished car)
    assert player1.car.velocity.x == initial_v1
    assert player2.car.velocity.x == initial_v2


def test_collision_integration_in_tick():
    """Test that collisions are handled during normal game ticks."""
    track = create_test_track()
    engine = GameEngine(track)

    player1 = engine.add_player("player1")
    player2 = engine.add_player("player2")

    # Position cars on collision course
    player1.car.position = Vector2(100, 0)
    player2.car.position = Vector2(130, 0)

    # Set inputs to accelerate toward each other
    player1.input.accelerate = True
    player2.input.accelerate = True
    player2.car.heading = math.pi  # Facing left

    engine.start_race()
    engine.state.race_info.status = RaceStatus.RACING
    engine.state.race_info.start_time = 0.0

    # Run several ticks
    for _ in range(30):  # ~0.5 seconds at 60Hz
        engine._tick()

    # Check that cars either collided or are still separated
    dx = player2.car.position.x - player1.car.position.x
    dy = player2.car.position.y - player1.car.position.y
    distance = (dx * dx + dy * dy) ** 0.5

    # Cars should not be overlapping
    assert distance >= 18  # Allow some margin for collision detection
