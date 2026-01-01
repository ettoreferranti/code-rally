"""
Surface Aware Racer - Template for Intermediate Users

This bot adapts its driving style based on the surface type.
Rally stages have different surfaces with varying grip levels.

Learning Goals:
- Reading surface type data
- Adapting speed to conditions
- Using dictionaries for configuration
- Strategic nitro usage

Difficulty: ★★☆☆☆ (Intermediate)
"""


class SurfaceAwareRacer(GuardedBotBase):
    """
    An intermediate bot that adjusts driving style based on surface conditions.

    Strategy:
    1. Maintain different maximum speeds for each surface type
    2. Brake when exceeding safe speed for current surface
    3. Use nitro strategically on asphalt (best grip)
    4. Steer based on raycast sensors
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
        # STEP 3: Calculate Steering
        # ============================================================

        # Use raycasts to determine steering direction
        steering = self.calculate_steering(state)

        # steering is a number:
        # - Negative value = turn left
        # - Positive value = turn right
        # - Close to zero = go straight


        # ============================================================
        # STEP 4: Make Speed Decisions
        # ============================================================

        # BRAKING: Brake if going too fast for current surface
        should_brake = going_too_fast

        # ACCELERATION: Accelerate if below safe speed
        should_accelerate = not going_too_fast

        # NITRO: Use on good surfaces when not going too fast
        # Only activate if:
        # 1. We have nitro charges
        # 2. Current surface is good for nitro
        # 3. We're not already going too fast
        # 4. We're going reasonably straight (small steering angle)
        should_use_nitro = (
            has_nitro
            and current_surface in self.nitro_surfaces
            and not going_too_fast
            and abs(steering) < 0.3  # Not turning sharply
        )


        # ============================================================
        # STEP 5: Return Actions
        # ============================================================

        return BotActions(
            accelerate=should_accelerate,
            brake=should_brake,
            turn_left=steering < -0.1,   # Turn left if steering is negative
            turn_right=steering > 0.1,    # Turn right if steering is positive
            use_nitro=should_use_nitro
        )


    def calculate_steering(self, state):
        """
        Helper method to calculate steering direction using raycasts.

        Args:
            state: Game state with raycast data

        Returns:
            float: Steering value (negative = left, positive = right)
        """
        # Get relevant raycasts
        # rays[0] = straight ahead
        # rays[2] = 45 degrees left
        # rays[4] = 45 degrees right

        left_distance = state.rays[2].distance
        right_distance = state.rays[4].distance

        # Calculate steering based on clearance difference
        # If left has more clearance, return negative (turn left)
        # If right has more clearance, return positive (turn right)
        #
        # Divide by 100 to normalize the value to a reasonable range
        steering = (right_distance - left_distance) / 100.0

        # Clamp steering to reasonable range (-1.0 to 1.0)
        steering = max(-1.0, min(1.0, steering))

        return steering


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
