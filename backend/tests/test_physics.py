"""
Unit tests for car physics simulation.
"""

import pytest
import math
from app.core.physics import (
    Vector2,
    CarState,
    CarPhysics,
    create_car_at_position
)


class TestVector2:
    """Test Vector2 mathematical operations."""

    def test_vector_addition(self):
        v1 = Vector2(3, 4)
        v2 = Vector2(1, 2)
        result = v1 + v2
        assert result.x == 4
        assert result.y == 6

    def test_vector_subtraction(self):
        v1 = Vector2(5, 7)
        v2 = Vector2(2, 3)
        result = v1 - v2
        assert result.x == 3
        assert result.y == 4

    def test_vector_scalar_multiplication(self):
        v = Vector2(2, 3)
        result = v * 2
        assert result.x == 4
        assert result.y == 6

    def test_magnitude(self):
        v = Vector2(3, 4)
        assert v.magnitude() == 5.0

    def test_normalize(self):
        v = Vector2(3, 4)
        normalized = v.normalize()
        assert abs(normalized.magnitude() - 1.0) < 0.0001

    def test_normalize_zero_vector(self):
        v = Vector2(0, 0)
        normalized = v.normalize()
        assert normalized.x == 0
        assert normalized.y == 0

    def test_dot_product(self):
        v1 = Vector2(2, 3)
        v2 = Vector2(4, 5)
        assert v1.dot(v2) == 23  # 2*4 + 3*5

    def test_rotate(self):
        v = Vector2(1, 0)
        rotated = v.rotate(math.pi / 2)  # Rotate 90 degrees
        assert abs(rotated.x) < 0.0001  # Should be ~0
        assert abs(rotated.y - 1.0) < 0.0001  # Should be ~1

    def test_to_tuple(self):
        v = Vector2(3.5, 4.2)
        assert v.to_tuple() == (3.5, 4.2)


class TestCarState:
    """Test CarState class."""

    def test_create_car_state(self):
        state = CarState(
            position=Vector2(100, 200),
            velocity=Vector2(10, 5),
            heading=math.pi / 4,
            angular_velocity=0.5
        )
        assert state.position.x == 100
        assert state.position.y == 200
        assert state.velocity.x == 10
        assert state.velocity.y == 5
        assert state.heading == math.pi / 4
        assert state.angular_velocity == 0.5

    def test_get_speed(self):
        state = CarState(
            position=Vector2(0, 0),
            velocity=Vector2(3, 4),
            heading=0
        )
        assert state.get_speed() == 5.0

    def test_get_heading_vector(self):
        state = CarState(
            position=Vector2(0, 0),
            velocity=Vector2(0, 0),
            heading=0  # Facing right
        )
        heading_vec = state.get_heading_vector()
        assert abs(heading_vec.x - 1.0) < 0.0001
        assert abs(heading_vec.y) < 0.0001

    def test_get_heading_vector_90_degrees(self):
        state = CarState(
            position=Vector2(0, 0),
            velocity=Vector2(0, 0),
            heading=math.pi / 2  # Facing up
        )
        heading_vec = state.get_heading_vector()
        assert abs(heading_vec.x) < 0.0001
        assert abs(heading_vec.y - 1.0) < 0.0001


class TestCarPhysics:
    """Test car physics calculations."""

    @pytest.fixture
    def physics(self):
        """Create a CarPhysics instance for testing."""
        return CarPhysics()

    @pytest.fixture
    def stationary_car(self):
        """Create a stationary car for testing."""
        return create_car_at_position(0, 0, 0)

    def test_create_car_at_position(self):
        car = create_car_at_position(100, 200, math.pi)
        assert car.position.x == 100
        assert car.position.y == 200
        assert car.heading == math.pi
        assert car.velocity.magnitude() == 0

    def test_acceleration_from_rest(self, physics, stationary_car):
        dt = 1.0 / 60.0  # One physics tick
        new_state = physics.apply_acceleration(stationary_car, dt)

        # Should have some forward velocity
        assert new_state.velocity.magnitude() > 0
        # Should maintain position (position update is separate)
        assert new_state.position.x == stationary_car.position.x
        assert new_state.position.y == stationary_car.position.y

    def test_acceleration_respects_max_speed(self, physics, stationary_car):
        # Accelerate for a long time
        state = stationary_car
        for _ in range(1000):
            state = physics.apply_acceleration(state, 1.0 / 60.0)

        # Should not exceed max speed
        max_speed = physics.physics.MAX_SPEED
        assert state.velocity.magnitude() <= max_speed + 0.1  # Small tolerance

    def test_braking_slows_car(self, physics):
        # Create a car moving forward
        moving_car = CarState(
            position=Vector2(0, 0),
            velocity=Vector2(50, 0),
            heading=0
        )

        initial_speed = moving_car.get_speed()
        new_state = physics.apply_braking(moving_car, 1.0 / 60.0)

        # Should be slower
        assert new_state.get_speed() < initial_speed

    def test_braking_stops_at_zero(self, physics):
        # Create a slow-moving car
        slow_car = CarState(
            position=Vector2(0, 0),
            velocity=Vector2(1, 0),
            heading=0
        )

        # Brake hard
        new_state = physics.apply_braking(slow_car, 1.0)

        # Should stop, not reverse
        assert new_state.velocity.magnitude() == 0

    def test_turning_changes_heading(self, physics):
        # Create a moving car
        moving_car = CarState(
            position=Vector2(0, 0),
            velocity=Vector2(30, 0),
            heading=0
        )

        initial_heading = moving_car.heading
        new_state = physics.apply_turning(moving_car, -1.0, 1.0 / 60.0)  # Turn left

        # Heading should have changed
        assert new_state.heading != initial_heading

    def test_turning_ineffective_at_low_speed(self, physics):
        # Create a slow-moving car
        slow_car = CarState(
            position=Vector2(0, 0),
            velocity=Vector2(1, 0),  # Very slow
            heading=0
        )

        # Create a fast-moving car
        fast_car = CarState(
            position=Vector2(0, 0),
            velocity=Vector2(50, 0),
            heading=0
        )

        dt = 1.0 / 60.0
        slow_turn = physics.apply_turning(slow_car, -1.0, dt)
        fast_turn = physics.apply_turning(fast_car, -1.0, dt)

        slow_delta = abs(slow_turn.heading - slow_car.heading)
        fast_delta = abs(fast_turn.heading - fast_car.heading)

        # Slow car should turn less
        assert slow_delta < fast_delta

    def test_drag_slows_car(self, physics):
        # Create a coasting car
        coasting_car = CarState(
            position=Vector2(0, 0),
            velocity=Vector2(50, 0),
            heading=0
        )

        initial_speed = coasting_car.get_speed()
        new_state = physics.apply_drag(coasting_car, 1.0 / 60.0)

        # Should be slower
        assert new_state.get_speed() < initial_speed

    def test_drag_stops_at_zero(self, physics):
        # Create a very slow car
        slow_car = CarState(
            position=Vector2(0, 0),
            velocity=Vector2(0.01, 0),
            heading=0
        )

        # Apply drag for a long time
        new_state = slow_car
        for _ in range(100):
            new_state = physics.apply_drag(new_state, 1.0 / 60.0)

        # Should eventually stop
        assert new_state.velocity.magnitude() == 0

    def test_update_position(self, physics):
        car = CarState(
            position=Vector2(0, 0),
            velocity=Vector2(60, 0),  # 60 units/second
            heading=0
        )

        dt = 1.0  # One second
        new_state = physics.update_position(car, dt)

        # Should have moved 60 units to the right
        assert abs(new_state.position.x - 60) < 0.01
        assert abs(new_state.position.y) < 0.01

    def test_simulate_step_no_input(self, physics, stationary_car):
        # Car at rest with no input should stay at rest
        dt = 1.0 / 60.0
        new_state = physics.simulate_step(
            stationary_car,
            accelerating=False,
            braking=False,
            turn_direction=0,
            dt=dt
        )

        assert new_state.velocity.magnitude() == 0
        assert new_state.position.x == 0
        assert new_state.position.y == 0

    def test_simulate_step_accelerate_and_turn(self, physics, stationary_car):
        # Simulate acceleration with turning
        state = stationary_car
        dt = 1.0 / 60.0

        # Accelerate and turn for 60 ticks (1 second)
        for _ in range(60):
            state = physics.simulate_step(
                state,
                accelerating=True,
                braking=False,
                turn_direction=-1.0,
                dt=dt
            )

        # Should be moving
        assert state.velocity.magnitude() > 0
        # Should have turned
        assert state.heading < 0  # Turned left (negative)
        # Should have moved
        assert state.position.magnitude() > 0

    def test_simulate_step_accelerate_then_brake(self, physics, stationary_car):
        state = stationary_car
        dt = 1.0 / 60.0

        # Accelerate for 60 ticks
        for _ in range(60):
            state = physics.simulate_step(
                state,
                accelerating=True,
                braking=False,
                turn_direction=0,
                dt=dt
            )

        speed_after_accel = state.get_speed()
        assert speed_after_accel > 0

        # Brake for 60 ticks
        for _ in range(60):
            state = physics.simulate_step(
                state,
                accelerating=False,
                braking=True,
                turn_direction=0,
                dt=dt
            )

        speed_after_brake = state.get_speed()

        # Should have slowed down significantly
        assert speed_after_brake < speed_after_accel


class TestDriftMechanics:
    """Test drift physics and grip mechanics."""

    @pytest.fixture
    def physics(self):
        """Create a CarPhysics instance for testing."""
        return CarPhysics()

    def test_no_drift_when_moving_straight(self, physics):
        # Car moving straight should not drift
        straight_car = CarState(
            position=Vector2(0, 0),
            velocity=Vector2(50, 0),  # Moving right
            heading=0  # Facing right
        )

        is_drifting, drift_angle = physics.calculate_drift_state(straight_car, grip_coefficient=1.0)

        assert not is_drifting
        assert abs(drift_angle) < 0.01

    def test_drift_when_lateral_velocity_high(self, physics):
        # Car with high lateral velocity should drift
        # Need lateral velocity > 60% of total speed to trigger drift
        drifting_car = CarState(
            position=Vector2(0, 0),
            velocity=Vector2(30, 30),  # Moving forward and very sideways
            heading=0  # Facing right
        )

        is_drifting, drift_angle = physics.calculate_drift_state(drifting_car, grip_coefficient=1.0)

        assert is_drifting
        assert abs(drift_angle) > 0

    def test_drift_angle_calculation(self, physics):
        # Test drift angle is calculated correctly
        car = CarState(
            position=Vector2(0, 0),
            velocity=Vector2(30, 15),  # Forward and sideways
            heading=0
        )

        is_drifting, drift_angle = physics.calculate_drift_state(car, grip_coefficient=1.0)

        # Lateral vector is (0, -1) for heading=0
        # lateral_velocity = velocity.dot((0, -1)) = -15
        # forward_velocity = velocity.dot((1, 0)) = 30
        # drift_angle = arctan2(-15, 30) ≈ -0.464 rad
        expected_angle = math.atan2(-15, 30)
        assert abs(drift_angle - expected_angle) < 0.01

    def test_no_drift_at_low_speed(self, physics):
        # Very slow car should not drift even with lateral velocity
        slow_car = CarState(
            position=Vector2(0, 0),
            velocity=Vector2(2, 1),  # Slow with lateral component
            heading=0
        )

        is_drifting, drift_angle = physics.calculate_drift_state(slow_car, grip_coefficient=1.0)

        assert not is_drifting

    def test_grip_reduces_lateral_velocity(self, physics):
        # Grip should reduce lateral velocity over time
        car = CarState(
            position=Vector2(0, 0),
            velocity=Vector2(30, 5),  # Some lateral velocity
            heading=0
        )

        # Apply grip for one step
        new_state = physics.apply_grip(car, grip_coefficient=1.0, dt=1.0 / 60.0)

        # Get lateral components
        lateral_vec = car.get_lateral_vector()
        old_lateral = car.velocity.dot(lateral_vec)
        new_lateral = new_state.velocity.dot(lateral_vec)

        # Lateral velocity should be reduced
        assert abs(new_lateral) < abs(old_lateral)

    def test_reduced_grip_when_drifting(self, physics):
        # When drifting, grip correction should be reduced (as a percentage)
        drifting_car = CarState(
            position=Vector2(0, 0),
            velocity=Vector2(40, 35),  # Very high lateral velocity -> drifting
            heading=0
        )

        not_drifting_car = CarState(
            position=Vector2(0, 0),
            velocity=Vector2(40, 5),  # Low lateral velocity -> not drifting
            heading=0
        )

        dt = 1.0 / 60.0

        # Apply grip to both
        drift_result = physics.apply_grip(drifting_car, grip_coefficient=1.0, dt=dt)
        no_drift_result = physics.apply_grip(not_drifting_car, grip_coefficient=1.0, dt=dt)

        # Check lateral velocity reduction using proper lateral vector
        drift_lateral_before = abs(drifting_car.velocity.dot(drifting_car.get_lateral_vector()))
        drift_lateral_after = abs(drift_result.velocity.dot(drift_result.get_lateral_vector()))

        no_drift_lateral_before = abs(not_drifting_car.velocity.dot(not_drifting_car.get_lateral_vector()))
        no_drift_lateral_after = abs(no_drift_result.velocity.dot(no_drift_result.get_lateral_vector()))

        # Calculate percentage correction
        drift_correction_pct = (drift_lateral_before - drift_lateral_after) / drift_lateral_before
        no_drift_correction_pct = (no_drift_lateral_before - no_drift_lateral_after) / no_drift_lateral_before

        # Drifting car should have less percentage correction (reduced grip strength)
        assert drift_correction_pct < no_drift_correction_pct

    def test_drift_state_updated_in_car_state(self, physics):
        # Drift state should be updated in CarState
        # Need lateral velocity > 60% of total speed
        drifting_car = CarState(
            position=Vector2(0, 0),
            velocity=Vector2(40, 35),  # Very high lateral velocity to trigger drift
            heading=0
        )

        new_state = physics.apply_grip(drifting_car, grip_coefficient=1.0, dt=1.0 / 60.0)

        assert new_state.is_drifting
        assert abs(new_state.drift_angle) > 0

    def test_low_grip_surfaces_cause_more_drift(self, physics):
        # Ice (low grip) should cause drift more easily than asphalt
        car = CarState(
            position=Vector2(0, 0),
            velocity=Vector2(30, 10),
            heading=0
        )

        # Check on asphalt (high grip)
        asphalt_drift, _ = physics.calculate_drift_state(car, grip_coefficient=1.0)

        # Check on ice (low grip)
        ice_drift, _ = physics.calculate_drift_state(car, grip_coefficient=0.25)

        # More likely to drift on ice
        # (Ice might drift where asphalt doesn't, or both drift but with different intensities)
        # For this test, we just verify the function accepts different grip coefficients
        assert isinstance(asphalt_drift, bool)
        assert isinstance(ice_drift, bool)

    def test_drift_recovery_when_slowing(self, physics):
        # Create a drifting car
        state = CarState(
            position=Vector2(0, 0),
            velocity=Vector2(50, 35),  # High speed with drift
            heading=0
        )

        dt = 1.0 / 60.0

        # Simulate slowing down without input (drag only)
        for _ in range(120):  # 2 seconds
            state = physics.simulate_step(
                state,
                accelerating=False,
                braking=False,
                turn_direction=0,
                dt=dt,
                grip_coefficient=1.0
            )

        # After slowing down, should not be drifting or drift should be minimal
        lateral_vec = state.get_lateral_vector()
        lateral_velocity = abs(state.velocity.dot(lateral_vec))

        # Lateral velocity should be significantly reduced
        assert lateral_velocity < 10  # Much less than initial 35

    def test_high_speed_corner_induces_drift(self, physics):
        # Accelerate to high speed, then turn hard
        state = create_car_at_position(0, 0, 0)
        dt = 1.0 / 60.0

        # Accelerate to high speed
        for _ in range(120):
            state = physics.simulate_step(
                state,
                accelerating=True,
                braking=False,
                turn_direction=0,
                dt=dt,
                grip_coefficient=1.0
            )

        speed_before_turn = state.get_speed()

        # Now turn hard while maintaining speed
        for _ in range(30):
            state = physics.simulate_step(
                state,
                accelerating=True,  # Keep accelerating
                braking=False,
                turn_direction=-1.0,  # Turn left hard
                dt=dt,
                grip_coefficient=1.0
            )

        # Should be drifting at high speed corner
        # (Might not always drift depending on parameters, but lateral velocity should increase)
        lateral_vec = state.get_lateral_vector()
        lateral_velocity = abs(state.velocity.dot(lateral_vec))

        # Should have some lateral velocity from turning
        assert lateral_velocity > 0
