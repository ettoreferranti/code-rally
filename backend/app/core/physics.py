"""
Physics simulation for CodeRally.

This module implements the car physics model with realistic acceleration,
braking, turning, drag, momentum, and drift mechanics.
"""

import math
from dataclasses import dataclass
from typing import Tuple

from app.config import get_settings


@dataclass
class Vector2:
    """2D vector for position and velocity calculations."""
    x: float
    y: float

    def __add__(self, other: 'Vector2') -> 'Vector2':
        return Vector2(self.x + other.x, self.y + other.y)

    def __sub__(self, other: 'Vector2') -> 'Vector2':
        return Vector2(self.x - other.x, self.y - other.y)

    def __mul__(self, scalar: float) -> 'Vector2':
        return Vector2(self.x * scalar, self.y * scalar)

    def magnitude(self) -> float:
        """Calculate the magnitude (length) of the vector."""
        return math.sqrt(self.x ** 2 + self.y ** 2)

    def normalize(self) -> 'Vector2':
        """Return a unit vector in the same direction."""
        mag = self.magnitude()
        if mag == 0:
            return Vector2(0, 0)
        return Vector2(self.x / mag, self.y / mag)

    def dot(self, other: 'Vector2') -> float:
        """Calculate dot product with another vector."""
        return self.x * other.x + self.y * other.y

    def rotate(self, angle: float) -> 'Vector2':
        """Rotate vector by angle (in radians)."""
        cos_a = math.cos(angle)
        sin_a = math.sin(angle)
        return Vector2(
            self.x * cos_a - self.y * sin_a,
            self.x * sin_a + self.y * cos_a
        )

    def to_tuple(self) -> Tuple[float, float]:
        """Convert to tuple (x, y)."""
        return (self.x, self.y)


@dataclass
class CarState:
    """
    Represents the physical state of a car.

    Attributes:
        position: Position in 2D space (units)
        velocity: Velocity vector (units/second)
        heading: Direction car is facing (radians, 0 = right, pi/2 = up)
        angular_velocity: Rate of rotation (radians/second)
        is_drifting: Whether the car is currently in a drift
        drift_angle: Angle between heading and velocity direction (radians)
    """
    position: Vector2
    velocity: Vector2
    heading: float
    angular_velocity: float = 0.0
    is_drifting: bool = False
    drift_angle: float = 0.0

    def get_speed(self) -> float:
        """Get current speed (magnitude of velocity)."""
        return self.velocity.magnitude()

    def get_heading_vector(self) -> Vector2:
        """Get unit vector in the direction the car is facing."""
        return Vector2(math.cos(self.heading), math.sin(self.heading))

    def get_lateral_vector(self) -> Vector2:
        """Get unit vector perpendicular to heading (right side of car)."""
        return Vector2(math.sin(self.heading), -math.cos(self.heading))


class CarPhysics:
    """
    Car physics simulation.

    Handles acceleration, braking, turning, drag, and momentum based on
    physics configuration.
    """

    def __init__(self):
        self.settings = get_settings()
        self.physics = self.settings.physics

    def apply_acceleration(self, state: CarState, dt: float) -> CarState:
        """
        Apply forward acceleration to the car.

        Args:
            state: Current car state
            dt: Time delta in seconds

        Returns:
            New car state with acceleration applied
        """
        heading_vec = state.get_heading_vector()
        acceleration = heading_vec * self.physics.ACCELERATION * dt

        new_velocity = state.velocity + acceleration

        # Clamp to max speed
        speed = new_velocity.magnitude()
        if speed > self.physics.MAX_SPEED:
            new_velocity = new_velocity.normalize() * self.physics.MAX_SPEED

        return CarState(
            position=state.position,
            velocity=new_velocity,
            heading=state.heading,
            angular_velocity=state.angular_velocity,
            is_drifting=state.is_drifting,
            drift_angle=state.drift_angle
        )

    def apply_braking(self, state: CarState, dt: float) -> CarState:
        """
        Apply braking force to slow the car.

        Args:
            state: Current car state
            dt: Time delta in seconds

        Returns:
            New car state with braking applied
        """
        if state.velocity.magnitude() == 0:
            return state

        # Brake in opposite direction of movement
        brake_direction = state.velocity.normalize() * -1
        brake_force = brake_direction * self.physics.BRAKE_FORCE * dt

        new_velocity = state.velocity + brake_force

        # Don't reverse from braking, just stop
        if state.velocity.dot(new_velocity) < 0:
            new_velocity = Vector2(0, 0)

        return CarState(
            position=state.position,
            velocity=new_velocity,
            heading=state.heading,
            angular_velocity=state.angular_velocity,
            is_drifting=state.is_drifting,
            drift_angle=state.drift_angle
        )

    def apply_turning(self, state: CarState, turn_direction: float, dt: float) -> CarState:
        """
        Apply turning input to rotate the car.

        Args:
            state: Current car state
            turn_direction: -1 for left, +1 for right, 0 for straight
            dt: Time delta in seconds

        Returns:
            New car state with turning applied
        """
        speed = state.get_speed()

        # Turning is less effective at low speeds
        if speed < self.physics.MIN_TURN_SPEED:
            speed_factor = speed / self.physics.MIN_TURN_SPEED
        else:
            speed_factor = 1.0

        # Calculate angular velocity
        turn_rate = self.physics.TURN_RATE * turn_direction * speed_factor

        # Update heading
        new_heading = state.heading + turn_rate * dt

        # Normalize heading to [-pi, pi]
        new_heading = (new_heading + math.pi) % (2 * math.pi) - math.pi

        return CarState(
            position=state.position,
            velocity=state.velocity,
            heading=new_heading,
            angular_velocity=turn_rate,
            is_drifting=state.is_drifting,
            drift_angle=state.drift_angle
        )

    def apply_drag(self, state: CarState, dt: float) -> CarState:
        """
        Apply drag/friction to slow the car over time.

        Args:
            state: Current car state
            dt: Time delta in seconds

        Returns:
            New car state with drag applied
        """
        speed = state.get_speed()

        # Already stopped or very slow - just stop completely
        if speed < 0.1:
            return CarState(
                position=state.position,
                velocity=Vector2(0, 0),
                heading=state.heading,
                angular_velocity=state.angular_velocity
            )

        # Drag is proportional to velocity squared
        drag_magnitude = self.physics.DRAG_COEFFICIENT * speed * dt

        drag_force = state.velocity.normalize() * -drag_magnitude
        new_velocity = state.velocity + drag_force

        # Don't reverse from drag, just stop
        if state.velocity.dot(new_velocity) < 0:
            new_velocity = Vector2(0, 0)

        return CarState(
            position=state.position,
            velocity=new_velocity,
            heading=state.heading,
            angular_velocity=state.angular_velocity,
            is_drifting=state.is_drifting,
            drift_angle=state.drift_angle
        )

    def calculate_drift_state(self, state: CarState, grip_coefficient: float = 1.0) -> Tuple[bool, float]:
        """
        Calculate whether the car is drifting and the drift angle.

        Args:
            state: Current car state
            grip_coefficient: Surface grip coefficient (0-1)

        Returns:
            Tuple of (is_drifting, drift_angle)
        """
        if state.get_speed() < self.physics.MIN_TURN_SPEED:
            return (False, 0.0)

        # Get velocity components
        heading_vec = state.get_heading_vector()
        lateral_vec = state.get_lateral_vector()

        # Calculate lateral velocity (sideways movement)
        lateral_velocity = state.velocity.dot(lateral_vec)
        forward_velocity = state.velocity.dot(heading_vec)

        # Calculate slip angle (angle between heading and velocity)
        if abs(forward_velocity) > 0.1:
            drift_angle = math.atan2(lateral_velocity, forward_velocity)
        else:
            drift_angle = 0.0

        # Check if exceeding grip threshold
        lateral_speed = abs(lateral_velocity)
        max_lateral_grip = grip_coefficient * self.physics.DRIFT_THRESHOLD * state.get_speed()

        is_drifting = lateral_speed > max_lateral_grip

        return (is_drifting, drift_angle)

    def apply_grip(
        self,
        state: CarState,
        grip_coefficient: float = 1.0,
        dt: float = 1.0 / 60.0
    ) -> CarState:
        """
        Apply grip forces to align velocity with heading.

        When not drifting, grip strongly aligns velocity with heading.
        When drifting, grip is reduced, allowing the car to slide.

        Args:
            state: Current car state
            grip_coefficient: Surface grip coefficient (0-1, default asphalt = 1.0)
            dt: Time delta in seconds

        Returns:
            New car state with grip applied
        """
        if state.get_speed() < 0.1:
            return state

        # Determine drift state
        is_drifting, drift_angle = self.calculate_drift_state(state, grip_coefficient)

        # Get velocity components
        heading_vec = state.get_heading_vector()
        lateral_vec = state.get_lateral_vector()

        forward_velocity = state.velocity.dot(heading_vec)
        lateral_velocity = state.velocity.dot(lateral_vec)

        # Apply grip to reduce lateral velocity
        if is_drifting:
            # Reduced grip when drifting
            grip_strength = grip_coefficient * 0.3
        else:
            # Full grip when not drifting
            grip_strength = grip_coefficient

        # Calculate grip force to reduce lateral slip
        lateral_correction = -lateral_velocity * grip_strength * self.physics.DRIFT_RECOVERY_RATE * dt

        # Apply correction
        new_lateral_velocity = lateral_velocity + lateral_correction

        # Reconstruct velocity vector
        new_velocity = (heading_vec * forward_velocity) + (lateral_vec * new_lateral_velocity)

        return CarState(
            position=state.position,
            velocity=new_velocity,
            heading=state.heading,
            angular_velocity=state.angular_velocity,
            is_drifting=is_drifting,
            drift_angle=drift_angle
        )

    def update_position(self, state: CarState, dt: float) -> CarState:
        """
        Update car position based on velocity.

        Args:
            state: Current car state
            dt: Time delta in seconds

        Returns:
            New car state with updated position
        """
        new_position = state.position + state.velocity * dt

        return CarState(
            position=new_position,
            velocity=state.velocity,
            heading=state.heading,
            angular_velocity=state.angular_velocity,
            is_drifting=state.is_drifting,
            drift_angle=state.drift_angle
        )

    def simulate_step(
        self,
        state: CarState,
        accelerating: bool,
        braking: bool,
        turn_direction: float,
        dt: float,
        grip_coefficient: float = 1.0
    ) -> CarState:
        """
        Simulate one physics step with the given inputs.

        Args:
            state: Current car state
            accelerating: True if accelerate input is active
            braking: True if brake input is active
            turn_direction: -1 for left, +1 for right, 0 for straight
            dt: Time delta in seconds
            grip_coefficient: Surface grip coefficient (0-1, default asphalt = 1.0)

        Returns:
            New car state after simulation step
        """
        new_state = state

        # Apply inputs
        if accelerating:
            new_state = self.apply_acceleration(new_state, dt)

        if braking:
            new_state = self.apply_braking(new_state, dt)

        if turn_direction != 0:
            new_state = self.apply_turning(new_state, turn_direction, dt)

        # Apply grip forces (handles drift mechanics)
        new_state = self.apply_grip(new_state, grip_coefficient, dt)

        # Always apply drag
        new_state = self.apply_drag(new_state, dt)

        # Update position
        new_state = self.update_position(new_state, dt)

        return new_state


def create_car_at_position(x: float, y: float, heading: float = 0.0) -> CarState:
    """
    Create a new car at the specified position.

    Args:
        x: X coordinate
        y: Y coordinate
        heading: Initial heading in radians (default: 0 = facing right)

    Returns:
        New CarState at the specified position
    """
    return CarState(
        position=Vector2(x, y),
        velocity=Vector2(0, 0),
        heading=heading,
        angular_velocity=0.0
    )
