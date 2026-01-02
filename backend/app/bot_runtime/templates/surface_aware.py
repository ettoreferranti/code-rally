"""
Surface Aware Racer - Template for Intermediate Users

This bot navigates toward checkpoints while adapting driving style based on surface type.
Rally stages have different surfaces with varying grip levels.

Learning Goals:
- Checkpoint navigation with math
- Reading surface type data
- Adapting speed to conditions
- Using dictionaries for configuration
- Strategic nitro usage

Difficulty: ★★☆☆☆ (Intermediate)
"""

import math


class SurfaceAwareRacer(GuardedBotBase):
    """
    An intermediate bot that navigates to checkpoints while adapting to surface conditions.

    Strategy:
    1. Navigate toward checkpoints using angle calculations
    2. Maintain different maximum speeds for each surface type
    3. Brake when exceeding safe speed or making sharp turns
    4. Use nitro strategically on good surfaces
    """

    def __init__(self):
        """Initialize the bot with surface-specific configuration."""
        self.name = "Surface Aware Racer"

        # Configuration: Maximum safe speed for each surface type
        # Lower values = more cautious, Higher values = more aggressive
        self.max_speeds = {
            "asphalt": 100,  # Best grip - can go fast
            "wet": 70,       # Reduced grip - moderate speed
            "gravel": 60,    # Low grip - need to slow down
            "ice": 40        # Very low grip - very slow
        }

        # Nitro strategy: Only use on surfaces with good grip
        self.nitro_surfaces = {"asphalt", "wet"}

        # Steering configuration
        self.steering_threshold = 0.1


    def on_tick(self, state):
        """
        Main racing logic - adapts to surface conditions.

        Args:
            state: Complete game state with all sensor data

        Returns:
            BotActions with driving decisions
        """

        # ============================================================
        # STEP 1: Read Current Conditions
        # ============================================================

        # What surface are we currently on?
        current_surface = state.car.current_surface

        # How fast are we going?
        current_speed = state.car.speed

        # Do we have nitro available?
        has_nitro = state.car.nitro_charges > 0


        # ============================================================
        # STEP 2: Determine Safe Speed for Current Surface
        # ============================================================

        # Look up the maximum safe speed for this surface
        # If surface is unknown, use a conservative default of 50
        safe_max_speed = self.max_speeds.get(current_surface, 50)

        # Check if we're going too fast for this surface
        going_too_fast = current_speed > safe_max_speed


        # ============================================================
        # STEP 3: Calculate Steering (navigate to checkpoint)
        # ============================================================

        # Get next checkpoint
        checkpoints = state.track.checkpoints
        next_cp_idx = state.track.next_checkpoint

        # Check if finished
        if next_cp_idx >= len(checkpoints):
            return BotActions(accelerate=True, brake=False)

        # Calculate angle to checkpoint
        target = checkpoints[next_cp_idx]
        my_x = state.car.position[0]
        my_y = state.car.position[1]
        dx = target[0] - my_x
        dy = target[1] - my_y

        target_angle = math.atan2(dy, dx)
        angle_diff = target_angle - state.car.heading

        # Normalize angle
        while angle_diff > math.pi:
            angle_diff -= 2 * math.pi
        while angle_diff < -math.pi:
            angle_diff += 2 * math.pi


        # ============================================================
        # STEP 4: Make Speed Decisions
        # ============================================================

        # BRAKING: Brake if going too fast OR sharp turn needed
        should_brake = going_too_fast or abs(angle_diff) > 0.7

        # ACCELERATION: Accelerate if not braking
        should_accelerate = not should_brake

        # NITRO: Use on good surfaces when going straight
        should_use_nitro = (
            has_nitro
            and current_surface in self.nitro_surfaces
            and not going_too_fast
            and abs(angle_diff) < 0.3  # Not turning sharply
        )


        # ============================================================
        # STEP 5: Return Actions
        # ============================================================

        # Steer toward checkpoint
        should_turn_left = angle_diff > self.steering_threshold
        should_turn_right = angle_diff < -self.steering_threshold

        return BotActions(
            accelerate=should_accelerate,
            brake=should_brake,
            turn_left=should_turn_left,
            turn_right=should_turn_right,
            use_nitro=should_use_nitro
        )


    # ================================================================
    # Optional: Enhanced Event Handlers
    # ================================================================

    def on_collision(self, event):
        """
        React to collisions by adjusting strategy.

        Args:
            event: Collision event with details
        """
        # You could track collision count and reduce aggression
        # Example: self.max_speeds["asphalt"] -= 5  # Slow down after crashes
        pass


    def on_checkpoint(self, checkpoint_index, split_time):
        """
        Track checkpoint performance.

        Args:
            checkpoint_index: Which checkpoint (0, 1, 2, ...)
            split_time: Time in seconds since race start
        """
        # You could use this to analyze your performance
        # Example: Compare split_time to previous races
        pass


    def on_finish(self, finish_time, final_position):
        """
        Called when crossing the finish line.

        Args:
            finish_time: Total time in seconds
            final_position: Final position (1st, 2nd, etc.)
        """
        # Celebrate!
        pass


# ====================================================================
# Tips for Improving This Bot:
# ====================================================================
#
# 1. TUNE SURFACE SPEEDS
#    - Experiment with the max_speeds dictionary
#    - Try more aggressive or conservative values
#    - Example: {"asphalt": 120, "wet": 80, "gravel": 70, "ice": 50}
#
# 2. LOOK AHEAD
#    - Use state.track.upcoming_surface to prepare for surface changes
#    - Start braking BEFORE hitting gravel or ice
#    - Example:
#      if state.track.upcoming_surface == "ice":
#          safe_max_speed -= 20  # Slow down early
#
# 3. ADAPTIVE LEARNING
#    - Use self.memory to track which speeds work best
#    - Save split times and adjust max_speeds between races
#    - Example:
#      if "best_asphalt_speed" not in self.memory:
#          self.memory["best_asphalt_speed"] = 100
#
# 4. CORNER AWARENESS
#    - Check state.track.upcoming_turn and state.track.turn_sharpness
#    - Reduce speed for sharp turns even on good surfaces
#    - Example:
#      if state.track.turn_sharpness > 0.7:
#          safe_max_speed -= 20
#
# 5. OFF-TRACK DETECTION
#    - Check state.car.off_track
#    - Slow down significantly when off track
#    - Example:
#      if state.car.off_track:
#          return BotActions(accelerate=False, brake=True, ...)
#
# 6. OPPONENT AWARENESS
#    - Check state.opponents to avoid collisions
#    - Slow down if opponent is directly ahead
#    - Example:
#      for opponent in state.opponents:
#          if opponent.distance < 20 and abs(opponent.relative_angle) < 0.3:
#              should_brake = True
#
# ====================================================================
