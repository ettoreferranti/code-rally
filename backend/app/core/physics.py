"""
Physics simulation for CodeRally.

This module implements the car physics model with realistic acceleration,
braking, turning, drag, and momentum.
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
    """
    position: Vector2
    velocity: Vector2
    heading: float
    angular_velocity: float = 0.0

    def get_speed(self) -> float:
        """Get current speed (magnitude of velocity)."""
        return self.velocity.magnitude()

    def get_heading_vector(self) -> Vector2:
        """Get unit vector in the direction the car is facing."""
        return Vector2(math.cos(self.heading), math.sin(self.heading))


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
            angular_velocity=state.angular_velocity
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
            angular_velocity=state.angular_velocity
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
            angular_velocity=turn_rate
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
            angular_velocity=state.angular_velocity
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
            angular_velocity=state.angular_velocity
        )

    def simulate_step(
        self,
        state: CarState,
        accelerating: bool,
        braking: bool,
        turn_direction: float,
        dt: float
    ) -> CarState:
        """
        Simulate one physics step with the given inputs.

        Args:
            state: Current car state
            accelerating: True if accelerate input is active
            braking: True if brake input is active
            turn_direction: -1 for left, +1 for right, 0 for straight
            dt: Time delta in seconds

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
