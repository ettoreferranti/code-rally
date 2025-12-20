"""
Bot lifecycle manager for integrating bots with the game engine.

This module manages bot instances, executes bot code at 20Hz, converts
game state to bot-friendly format, and handles bot errors gracefully.
"""

import logging
from typing import Optional, Any, Dict
import time

from app.bot_runtime.sandbox import BotSandbox, SandboxTimeoutError, SandboxSecurityError
from app.bot_runtime.types import (
    BotGameState,
    BotCarState,
    BotTrackState,
    BotRaceState,
    BotActions,
    BotRaycast,
    BotOpponent,
    CollisionEvent
)
from app.core.raycast import RaycastSystem
from app.core.physics import Vector2
from app.config import get_settings

logger = logging.getLogger(__name__)


class BotError(Exception):
    """Raised when a bot encounters an error during execution."""
    pass


class BotManager:
    """
    Manages bot lifecycle and integration with game engine.

    Responsibilities:
    - Load and validate bot code
    - Execute bots at 20Hz (every 3rd physics tick)
    - Convert game state to bot-friendly format
    - Handle bot errors gracefully (DQ bot, don't crash game)
    - Call event callbacks
    """

    def __init__(self):
        """Initialize bot manager."""
        self.settings = get_settings()
        self.sandbox = BotSandbox()
        self.raycast_system = RaycastSystem()

        # Track which physics tick to run bots on (20Hz = every 3rd tick at 60Hz)
        self.bot_tick_interval = self.settings.game.TICK_RATE // self.settings.bot.BOT_TICK_RATE

    def load_bot(self, code: str, class_name: str) -> Any:
        """
        Load and validate bot code, returning bot instance.

        Args:
            code: Python source code
            class_name: Name of bot class to instantiate

        Returns:
            Bot instance

        Raises:
            BotError: If bot code is invalid or cannot be loaded
        """
        try:
            bot_instance = self.sandbox.execute_bot_code(code, class_name)
            logger.info(f"Successfully loaded bot class '{class_name}'")
            return bot_instance
        except (SandboxSecurityError, SandboxTimeoutError, ValueError) as e:
            error_msg = f"Failed to load bot: {str(e)}"
            logger.error(error_msg)
            raise BotError(error_msg) from e

    def should_run_bot_tick(self, physics_tick: int) -> bool:
        """
        Determine if bots should run this physics tick.

        Bots run at 20Hz, which is every 3rd physics tick at 60Hz.

        Args:
            physics_tick: Current physics tick number

        Returns:
            True if bots should run this tick
        """
        return physics_tick % self.bot_tick_interval == 0

    def get_bot_actions(
        self,
        bot_instance: Any,
        game_state: 'GameState',
        player_id: str,
        track: 'Track'
    ) -> Optional[BotActions]:
        """
        Execute bot's on_tick() method and get actions.

        Args:
            bot_instance: Bot instance to execute
            game_state: Current game state
            player_id: ID of the player this bot controls
            track: Track being raced on

        Returns:
            BotActions if successful, None if bot error
        """
        try:
            # Convert game state to bot-friendly format
            bot_game_state = self._create_bot_game_state(game_state, player_id, track)

            # Call bot's on_tick() with timeout enforcement
            result = self.sandbox.call_on_tick(bot_instance, bot_game_state)

            # Convert result to BotActions
            if isinstance(result, dict):
                return BotActions.from_dict(result)
            else:
                # Bot returned invalid type - return safe default
                logger.warning(f"Bot returned invalid type: {type(result)}")
                return BotActions()

        except (SandboxTimeoutError, SandboxSecurityError) as e:
            # Critical error - bot should be DQ'd
            logger.error(f"Bot error in on_tick(): {str(e)}")
            raise BotError(f"Bot execution error: {str(e)}") from e
        except Exception as e:
            # Unexpected error - log and return safe default
            logger.error(f"Unexpected bot error: {str(e)}")
            return BotActions()

    def _create_bot_game_state(
        self,
        game_state: 'GameState',
        player_id: str,
        track: 'Track'
    ) -> BotGameState:
        """
        Convert game engine state to bot-friendly BotGameState.

        Args:
            game_state: Current game state from engine
            player_id: ID of player this bot controls
            track: Track being raced on

        Returns:
            BotGameState with all sensor data
        """
        from app.core.engine import GameState, PlayerState

        player = game_state.players[player_id]

        # Get all other cars for raycast detection
        other_cars = [
            p.car for pid, p in game_state.players.items()
            if pid != player_id
        ]

        # Cast raycasts for vision
        raycast_results = self.raycast_system.cast_all_rays(
            player.car,
            track,
            other_cars
        )

        # Convert raycasts to bot format
        bot_rays = [
            BotRaycast(
                distance=r.distance,
                hit_type=r.hit_type
            )
            for r in raycast_results
        ]

        # Create bot car state
        bot_car = BotCarState(
            position=(player.car.position.x, player.car.position.y),
            heading=player.car.heading,
            speed=player.car.velocity.magnitude(),
            velocity=(player.car.velocity.x, player.car.velocity.y),
            angular_velocity=player.car.angular_velocity,
            health=100.0,  # Future feature
            nitro_charges=player.car.nitro_charges,
            nitro_active=player.car.nitro_active,
            current_surface=self._get_surface_at_position(player.car.position, game_state, track),
            off_track=player.is_off_track
        )

        # Create track state
        next_checkpoint_idx = player.current_checkpoint
        checkpoints_list = [(cp.position[0], cp.position[1]) for cp in track.checkpoints]

        bot_track = BotTrackState(
            checkpoints=checkpoints_list,
            next_checkpoint=next_checkpoint_idx,
            distance_to_boundary_left=100.0,  # TODO: Calculate actual distances
            distance_to_boundary_right=100.0,
            upcoming_surface="asphalt",  # TODO: Look ahead for surface
            upcoming_turn="straight",  # TODO: Analyze track curvature
            turn_sharpness=0.0
        )

        # Create opponent list (fog of war - only show nearby opponents)
        bot_opponents = self._get_visible_opponents(player, game_state, player_id)

        # Create race state
        bot_race = BotRaceState(
            current_checkpoint=player.current_checkpoint,
            total_checkpoints=len(track.checkpoints),
            position=player.position or len(game_state.players),
            total_cars=len(game_state.players),
            elapsed_time=time.time() - game_state.race_info.start_time if game_state.race_info.start_time else 0.0,
            distance_to_finish=self._calculate_distance_to_finish(player, track)
        )

        return BotGameState(
            car=bot_car,
            track=bot_track,
            rays=bot_rays,
            opponents=bot_opponents,
            race=bot_race
        )

    def _get_surface_at_position(
        self,
        position: Vector2,
        game_state: 'GameState',
        track: 'Track'
    ) -> str:
        """Get surface type at position."""
        # Find closest track segment
        min_dist = float('inf')
        closest_surface = 'asphalt'

        for segment in track.segments:
            dx = position.x - segment.start.x
            dy = position.y - segment.start.y
            dist = (dx * dx + dy * dy) ** 0.5

            if dist < min_dist:
                min_dist = dist
                # Get surface type, handle both enum and string
                if hasattr(segment.start.surface, 'value'):
                    closest_surface = segment.start.surface.value.lower()
                else:
                    closest_surface = str(segment.start.surface).lower()

        return closest_surface

    def _get_visible_opponents(
        self,
        player: 'PlayerState',
        game_state: 'GameState',
        player_id: str
    ) -> list:
        """
        Get list of visible opponent cars (fog of war).

        Args:
            player: Player making the observation
            game_state: Current game state
            player_id: ID of player

        Returns:
            List of BotOpponent objects for nearby cars
        """
        import math
        from app.core.engine import PlayerState

        opponents = []
        visibility_radius = self.settings.bot.OPPONENT_VISIBILITY_RADIUS  # TODO: Add to config

        for pid, opponent in game_state.players.items():
            if pid == player_id:
                continue

            # Calculate distance
            dx = opponent.car.position.x - player.car.position.x
            dy = opponent.car.position.y - player.car.position.y
            distance = math.sqrt(dx * dx + dy * dy)

            # Only show opponents within visibility radius
            if distance <= visibility_radius:
                # Calculate relative angle
                angle_to_opponent = math.atan2(dy, dx)
                relative_angle = angle_to_opponent - player.car.heading

                # Normalize to [-π, π]
                relative_angle = (relative_angle + math.pi) % (2 * math.pi) - math.pi

                opponents.append(BotOpponent(
                    position=(opponent.car.position.x, opponent.car.position.y),
                    velocity=(opponent.car.velocity.x, opponent.car.velocity.y),
                    heading=opponent.car.heading,
                    distance=distance,
                    relative_angle=relative_angle
                ))

        return opponents

    def _calculate_distance_to_finish(self, player: 'PlayerState', track: 'Track') -> float:
        """
        Calculate approximate distance to finish line.

        Args:
            player: Player to calculate for
            track: Track being raced on

        Returns:
            Approximate distance in track units
        """
        # Simple estimate: sum of distances to remaining checkpoints
        distance = 0.0

        if player.current_checkpoint >= len(track.checkpoints):
            return 0.0  # Already finished

        # Distance to next checkpoint
        next_cp = track.checkpoints[player.current_checkpoint]
        dx = next_cp.position[0] - player.car.position.x
        dy = next_cp.position[1] - player.car.position.y
        distance += (dx * dx + dy * dy) ** 0.5

        # Add rough distance between remaining checkpoints (simplified)
        for i in range(player.current_checkpoint + 1, len(track.checkpoints)):
            distance += 100.0  # Rough estimate

        return distance

    def call_on_collision(
        self,
        bot_instance: Any,
        other_type: str,
        impact_speed: float,
        direction: float,
        other_id: Optional[str] = None
    ) -> None:
        """
        Call bot's on_collision() callback.

        Args:
            bot_instance: Bot instance
            other_type: Type of collision ("car", "boundary", "obstacle")
            impact_speed: Speed of impact
            direction: Direction of impact
            other_id: ID of other car if car collision
        """
        try:
            event = CollisionEvent(
                other_type=other_type,
                impact_speed=impact_speed,
                direction=direction,
                other_id=other_id
            )
            self.sandbox.call_on_collision(bot_instance, event)
        except SandboxTimeoutError as e:
            logger.warning(f"Bot on_collision() timeout: {str(e)}")
        except Exception as e:
            logger.warning(f"Bot on_collision() error: {str(e)}")

    def call_on_checkpoint(
        self,
        bot_instance: Any,
        checkpoint_index: int,
        split_time: float
    ) -> None:
        """
        Call bot's on_checkpoint() callback.

        Args:
            bot_instance: Bot instance
            checkpoint_index: Index of checkpoint passed
            split_time: Time since race start
        """
        try:
            self.sandbox.call_on_checkpoint(bot_instance, checkpoint_index, split_time)
        except SandboxTimeoutError as e:
            logger.warning(f"Bot on_checkpoint() timeout: {str(e)}")
        except Exception as e:
            logger.warning(f"Bot on_checkpoint() error: {str(e)}")

    def call_on_finish(
        self,
        bot_instance: Any,
        finish_time: float,
        final_position: int
    ) -> None:
        """
        Call bot's on_finish() callback.

        Args:
            bot_instance: Bot instance
            finish_time: Total race time
            final_position: Final race position
        """
        try:
            self.sandbox.call_on_finish(bot_instance, finish_time, final_position)
        except SandboxTimeoutError as e:
            logger.warning(f"Bot on_finish() timeout: {str(e)}")
        except Exception as e:
            logger.warning(f"Bot on_finish() error: {str(e)}")
