"""
Game engine for CodeRally - server-authoritative physics simulation.

This module implements the main game loop with fixed 60Hz tick rate,
managing game state, physics updates, and race progression.
"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple
from enum import Enum

from app.core.physics import CarPhysics, CarState, Vector2
from app.core.track import Track
from app.config import get_settings


class RaceStatus(Enum):
    """Current status of the race."""
    WAITING = "waiting"  # Waiting for players
    COUNTDOWN = "countdown"  # Countdown before start
    RACING = "racing"  # Race in progress
    FINISHED = "finished"  # Race complete


@dataclass
class PlayerInput:
    """Player input for a single frame."""
    accelerate: bool = False
    brake: bool = False
    turn_left: bool = False
    turn_right: bool = False
    nitro: bool = False


@dataclass
class RaceInfo:
    """Information about race progress."""
    status: RaceStatus = RaceStatus.WAITING
    start_time: Optional[float] = None
    countdown_remaining: float = 0.0
    finish_time: Optional[float] = None


@dataclass
class PlayerState:
    """Complete state for a single player."""
    player_id: str
    car: CarState
    input: PlayerInput = field(default_factory=PlayerInput)
    current_checkpoint: int = 0
    checkpoints_passed: Set[int] = field(default_factory=set)
    is_finished: bool = False
    finish_time: Optional[float] = None
    is_off_track: bool = False


@dataclass
class GameState:
    """Complete game state for a race."""
    track: Track
    players: Dict[str, PlayerState]
    race_info: RaceInfo
    tick: int = 0


class GameEngine:
    """
    Server-authoritative game engine with fixed 60Hz physics.

    Manages game state, processes player inputs, runs physics simulation,
    and tracks race progression.
    """

    def __init__(self, track: Track):
        """
        Initialize game engine with a track.

        Args:
            track: The track to race on
        """
        self.settings = get_settings()
        self.physics = CarPhysics()

        self.state = GameState(
            track=track,
            players={},
            race_info=RaceInfo()
        )

        self.tick_rate = self.settings.game.TICK_RATE
        self.tick_interval = 1.0 / self.tick_rate

        self._running = False
        self._task: Optional[asyncio.Task] = None

    def add_player(self, player_id: str) -> PlayerState:
        """
        Add a new player to the game.

        Args:
            player_id: Unique identifier for the player

        Returns:
            The created PlayerState
        """
        # Create car at track start position
        start_x, start_y = self.state.track.start_position
        car = CarState(
            position=Vector2(start_x, start_y),
            velocity=Vector2(0, 0),
            heading=self.state.track.start_heading,
            angular_velocity=0.0
        )

        player = PlayerState(
            player_id=player_id,
            car=car
        )

        self.state.players[player_id] = player
        return player

    def remove_player(self, player_id: str) -> None:
        """Remove a player from the game."""
        if player_id in self.state.players:
            del self.state.players[player_id]

    def update_player_input(self, player_id: str, input_data: PlayerInput) -> None:
        """
        Update a player's input state.

        Args:
            player_id: Player to update
            input_data: New input state
        """
        if player_id in self.state.players:
            self.state.players[player_id].input = input_data

    def start_race(self) -> None:
        """Start the race countdown."""
        self.state.race_info.status = RaceStatus.COUNTDOWN
        self.state.race_info.countdown_remaining = float(self.settings.game.COUNTDOWN_SECONDS)

    async def start_loop(self) -> None:
        """Start the game loop in the background."""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._game_loop())

    async def stop_loop(self) -> None:
        """Stop the game loop."""
        self._running = False
        if self._task:
            await self._task
            self._task = None

    async def _game_loop(self) -> None:
        """Main game loop - runs at fixed tick rate."""
        last_tick_time = time.perf_counter()

        while self._running:
            current_time = time.perf_counter()
            elapsed = current_time - last_tick_time

            # Wait until it's time for the next tick
            if elapsed < self.tick_interval:
                await asyncio.sleep(self.tick_interval - elapsed)
                continue

            last_tick_time = current_time

            # Run physics tick
            self._tick()

    def _tick(self) -> None:
        """Process one game tick (1/60th of a second)."""
        self.state.tick += 1

        # Update race status
        self._update_race_status()

        # Only update physics during active racing
        if self.state.race_info.status == RaceStatus.RACING:
            # Update each player's physics
            for player in self.state.players.values():
                if not player.is_finished:
                    self._update_player_physics(player)
                    self._check_checkpoint_progress(player)
                    self._check_finish(player)

    def _update_race_status(self) -> None:
        """Update race countdown and status."""
        if self.state.race_info.status == RaceStatus.COUNTDOWN:
            self.state.race_info.countdown_remaining -= self.tick_interval

            if self.state.race_info.countdown_remaining <= 0:
                # Start the race!
                self.state.race_info.status = RaceStatus.RACING
                self.state.race_info.start_time = time.time()
                self.state.race_info.countdown_remaining = 0.0

    def _update_player_physics(self, player: PlayerState) -> None:
        """
        Update physics for a single player.

        Args:
            player: Player to update
        """
        # Get surface at player position
        surface = self._get_surface_at_position(player.car.position)
        grip = self._get_grip_coefficient(surface)

        # Check if off-track
        player.is_off_track = not self._is_on_track(player.car.position)

        # Apply off-track penalties
        if player.is_off_track:
            grip *= self.settings.physics.OFF_TRACK_GRIP_MULTIPLIER

        # Convert input to turn direction
        turn_direction = 0.0
        if player.input.turn_right:
            turn_direction = 1.0
        elif player.input.turn_left:
            turn_direction = -1.0

        # Simulate physics step
        player.car = self.physics.simulate_step(
            state=player.car,
            accelerating=player.input.accelerate,
            braking=player.input.brake,
            turn_direction=turn_direction,
            dt=self.tick_interval,
            grip_coefficient=grip
        )

        # Handle collisions with obstacles
        self._handle_obstacle_collision(player)

        # Handle collisions with track boundaries
        self._handle_boundary_collision(player)

    def _get_surface_at_position(self, position: Vector2) -> str:
        """
        Determine the surface type at a position.

        Args:
            position: Position to check

        Returns:
            Surface type string (asphalt, wet, gravel, ice)
        """
        # Find closest track segment
        min_dist = float('inf')
        closest_surface = 'asphalt'

        for segment in self.state.track.segments:
            # Simple distance check to segment start point
            dx = position.x - segment.start.x
            dy = position.y - segment.start.y
            dist = (dx * dx + dy * dy) ** 0.5

            if dist < min_dist:
                min_dist = dist
                closest_surface = segment.start.surface

        return closest_surface

    def _get_grip_coefficient(self, surface) -> float:
        """Get grip coefficient for a surface type."""
        # Handle both SurfaceType enum and string
        if hasattr(surface, 'value'):
            surface_str = surface.value
        else:
            surface_str = surface

        surface_lower = surface_str.lower()
        if surface_lower == 'wet':
            return self.settings.physics.GRIP_WET
        elif surface_lower == 'gravel':
            return self.settings.physics.GRIP_GRAVEL
        elif surface_lower == 'ice':
            return self.settings.physics.GRIP_ICE
        else:
            return self.settings.physics.GRIP_ASPHALT

    def _is_on_track(self, position: Vector2) -> bool:
        """
        Check if a position is on the track.

        Args:
            position: Position to check

        Returns:
            True if on track, False if off-track
        """
        min_dist = float('inf')
        closest_segment = None

        # Find the closest point on any track segment
        for segment in self.state.track.segments:
            # Sample points along the segment
            num_samples = 20 if segment.control1 else 5

            for i in range(num_samples + 1):
                t = i / num_samples

                # Get point on track centerline
                if segment.is_straight():
                    x = segment.start.x + t * (segment.end.x - segment.start.x)
                    y = segment.start.y + t * (segment.end.y - segment.start.y)
                else:
                    # For curves, we need to import the bezier calculation
                    import math
                    # Cubic bezier formula
                    mt = 1 - t
                    mt2 = mt * mt
                    mt3 = mt2 * mt
                    t2 = t * t
                    t3 = t2 * t

                    p0 = (segment.start.x, segment.start.y)
                    p1 = segment.control1
                    p2 = segment.control2
                    p3 = (segment.end.x, segment.end.y)

                    x = mt3 * p0[0] + 3 * mt2 * t * p1[0] + 3 * mt * t2 * p2[0] + t3 * p3[0]
                    y = mt3 * p0[1] + 3 * mt2 * t * p1[1] + 3 * mt * t2 * p2[1] + t3 * p3[1]

                # Distance from car to this track point
                dx = position.x - x
                dy = position.y - y
                dist = (dx * dx + dy * dy) ** 0.5

                if dist < min_dist:
                    min_dist = dist
                    closest_segment = segment

        # On-track if within half the track width
        if closest_segment:
            track_half_width = closest_segment.start.width / 2
            return min_dist <= track_half_width

        return False

    def _handle_obstacle_collision(self, player: PlayerState) -> None:
        """
        Handle collision with obstacles.

        Args:
            player: Player to check for collisions
        """
        if not self.state.track.obstacles:
            return

        car_radius = 10.0  # TODO: Make configurable

        for obstacle in self.state.track.obstacles:
            obs_x, obs_y = obstacle.position
            dx = player.car.position.x - obs_x
            dy = player.car.position.y - obs_y
            distance = (dx * dx + dy * dy) ** 0.5

            collision_distance = car_radius + obstacle.radius

            if distance < collision_distance:
                # Calculate collision normal
                if distance > 0:
                    normal = Vector2(dx / distance, dy / distance)
                else:
                    normal = Vector2(1, 0)

                penetration = collision_distance - distance

                # Apply elastic bounce
                velocity_dot_normal = player.car.velocity.dot(normal)

                # Only bounce if moving into obstacle
                if velocity_dot_normal < 0:
                    elasticity = self.settings.physics.COLLISION_ELASTICITY
                    bounce = normal * (-(1 + elasticity) * velocity_dot_normal)
                    player.car.velocity = player.car.velocity + bounce

                # Push car out of obstacle
                player.car.position = player.car.position + (normal * penetration)

    def _handle_boundary_collision(self, player: PlayerState) -> None:
        """
        Handle collision with track containment boundaries.

        Args:
            player: Player to check for boundary collisions
        """
        if not self.state.track.containment:
            return

        car_radius = 10.0  # TODO: Make configurable

        # Check both left and right boundaries
        for boundary_points in [self.state.track.containment.left_points,
                                 self.state.track.containment.right_points]:
            # Check each boundary segment
            for i in range(len(boundary_points) - 1):
                p1_x, p1_y = boundary_points[i]
                p2_x, p2_y = boundary_points[i + 1]

                # Find closest point on line segment to car
                car_x = player.car.position.x
                car_y = player.car.position.y

                # Vector from p1 to p2
                seg_dx = p2_x - p1_x
                seg_dy = p2_y - p1_y
                seg_length_sq = seg_dx * seg_dx + seg_dy * seg_dy

                if seg_length_sq == 0:
                    # Degenerate segment, just use p1
                    closest_x, closest_y = p1_x, p1_y
                else:
                    # Parameter t for projection onto line segment
                    # t = 0 means p1, t = 1 means p2
                    t = max(0, min(1, ((car_x - p1_x) * seg_dx + (car_y - p1_y) * seg_dy) / seg_length_sq))

                    # Closest point on segment
                    closest_x = p1_x + t * seg_dx
                    closest_y = p1_y + t * seg_dy

                # Distance from car to closest point
                dx = car_x - closest_x
                dy = car_y - closest_y
                distance = (dx * dx + dy * dy) ** 0.5

                # Check if car is colliding with this boundary segment
                if distance < car_radius:
                    # Calculate collision normal (away from wall)
                    if distance > 0:
                        normal = Vector2(dx / distance, dy / distance)
                    else:
                        # Car is exactly on the wall, use perpendicular to segment
                        seg_length = seg_length_sq ** 0.5
                        if seg_length > 0:
                            # Perpendicular to segment (pointing away from track)
                            normal = Vector2(-seg_dy / seg_length, seg_dx / seg_length)
                        else:
                            normal = Vector2(1, 0)

                    penetration = car_radius - distance

                    # Apply elastic bounce
                    velocity_dot_normal = player.car.velocity.dot(normal)

                    # Only bounce if moving into wall
                    if velocity_dot_normal < 0:
                        elasticity = self.settings.physics.COLLISION_ELASTICITY
                        bounce = normal * (-(1 + elasticity) * velocity_dot_normal)
                        player.car.velocity = player.car.velocity + bounce

                    # Push car out of wall
                    player.car.position = player.car.position + (normal * penetration)

    def _check_checkpoint_progress(self, player: PlayerState) -> None:
        """
        Check if player has passed the next checkpoint.

        Args:
            player: Player to check
        """
        if player.current_checkpoint >= len(self.state.track.checkpoints):
            return

        checkpoint = self.state.track.checkpoints[player.current_checkpoint]
        cp_x, cp_y = checkpoint.position

        # Create checkpoint line perpendicular to its angle
        # The checkpoint angle points along the track direction
        # We want a line perpendicular to this
        import math
        perp_angle = checkpoint.angle + math.pi / 2

        # Calculate checkpoint line endpoints (perpendicular to track direction)
        half_width = checkpoint.width / 2
        line_p1_x = cp_x + math.cos(perp_angle) * half_width
        line_p1_y = cp_y + math.sin(perp_angle) * half_width
        line_p2_x = cp_x - math.cos(perp_angle) * half_width
        line_p2_y = cp_y - math.sin(perp_angle) * half_width

        # Check if car crossed the checkpoint line
        # We need the previous position to detect crossing
        if not hasattr(player, '_prev_position'):
            player._prev_position = player.car.position
            return

        prev_x = player._prev_position.x
        prev_y = player._prev_position.y
        curr_x = player.car.position.x
        curr_y = player.car.position.y

        # Check if line segments intersect (car path vs checkpoint line)
        crossed = self._line_segments_intersect(
            prev_x, prev_y, curr_x, curr_y,
            line_p1_x, line_p1_y, line_p2_x, line_p2_y
        )

        if crossed:
            # Check if crossing in the forward direction
            # Dot product of movement direction with checkpoint direction
            move_dx = curr_x - prev_x
            move_dy = curr_y - prev_y
            cp_dir_x = math.cos(checkpoint.angle)
            cp_dir_y = math.sin(checkpoint.angle)

            dot_product = move_dx * cp_dir_x + move_dy * cp_dir_y

            # Only count if moving forward through checkpoint
            if dot_product > 0:
                player.checkpoints_passed.add(player.current_checkpoint)
                player.current_checkpoint += 1

        # Update previous position for next frame
        player._prev_position = Vector2(curr_x, curr_y)

    def _line_segments_intersect(
        self,
        p1_x: float, p1_y: float, p2_x: float, p2_y: float,
        p3_x: float, p3_y: float, p4_x: float, p4_y: float
    ) -> bool:
        """
        Check if two line segments intersect.

        Uses the cross product method to determine if line segment p1-p2
        intersects with line segment p3-p4.

        Args:
            p1_x, p1_y: First point of first line segment
            p2_x, p2_y: Second point of first line segment
            p3_x, p3_y: First point of second line segment
            p4_x, p4_y: Second point of second line segment

        Returns:
            True if the line segments intersect, False otherwise
        """
        def ccw(ax: float, ay: float, bx: float, by: float, cx: float, cy: float) -> bool:
            """Check if three points are in counter-clockwise order."""
            return (cy - ay) * (bx - ax) > (by - ay) * (cx - ax)

        # Two segments intersect if the endpoints of each segment are on
        # opposite sides of the other segment
        return (ccw(p1_x, p1_y, p3_x, p3_y, p4_x, p4_y) != ccw(p2_x, p2_y, p3_x, p3_y, p4_x, p4_y) and
                ccw(p1_x, p1_y, p2_x, p2_y, p3_x, p3_y) != ccw(p1_x, p1_y, p2_x, p2_y, p4_x, p4_y))

    def _check_finish(self, player: PlayerState) -> None:
        """
        Check if player has finished the race.

        Args:
            player: Player to check
        """
        # Finished if all checkpoints passed
        if player.current_checkpoint >= len(self.state.track.checkpoints):
            if not player.is_finished:
                player.is_finished = True
                player.finish_time = time.time()

                # Check if all players finished
                all_finished = all(p.is_finished for p in self.state.players.values())
                if all_finished:
                    self.state.race_info.status = RaceStatus.FINISHED
                    self.state.race_info.finish_time = time.time()

    def get_state_snapshot(self) -> Dict:
        """
        Get current game state as JSON-serializable dict.

        Returns:
            Dictionary containing complete game state
        """
        return {
            'tick': self.state.tick,
            'race_info': {
                'status': self.state.race_info.status.value,
                'start_time': self.state.race_info.start_time,
                'countdown_remaining': self.state.race_info.countdown_remaining,
                'finish_time': self.state.race_info.finish_time,
            },
            'players': {
                player_id: {
                    'car': {
                        'position': {'x': player.car.position.x, 'y': player.car.position.y},
                        'velocity': {'x': player.car.velocity.x, 'y': player.car.velocity.y},
                        'heading': player.car.heading,
                        'angular_velocity': player.car.angular_velocity,
                        'is_drifting': player.car.is_drifting,
                        'drift_angle': player.car.drift_angle,
                    },
                    'current_checkpoint': player.current_checkpoint,
                    'is_finished': player.is_finished,
                    'finish_time': player.finish_time,
                    'is_off_track': player.is_off_track,
                }
                for player_id, player in self.state.players.items()
            }
        }
