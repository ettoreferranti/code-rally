"""
Checkpoint Navigator - Template for Advanced Users

This bot uses checkpoint positions and trigonometry to calculate
the optimal racing line. It navigates directly toward each checkpoint.

Learning Goals:
- Using checkpoint position data
- Trigonometry for angle calculations
- Predictive steering and braking
- The math module (only allowed import)

Difficulty: ★★★☆☆ (Advanced)
"""

import math  # The only module allowed in bot code!


class CheckpointNavigator(GuardedBotBase):
    """
    An advanced bot that navigates using checkpoint positions.

    Strategy:
    1. Calculate angle to next checkpoint
    2. Steer toward the checkpoint
    3. Brake for sharp turns
    4. Use nitro on straights
    """

    def __init__(self):
        """Initialize the navigator bot."""
        self.name = "Checkpoint Navigator"

        # Configuration
        self.steering_threshold = 0.1     # Deadzone for steering (radians)
        self.sharp_turn_threshold = 0.5   # Angle considered "sharp turn" (radians)
        self.nitro_angle_threshold = 0.2  # Max angle to use nitro (radians)


    def on_tick(self, state):
        """
        Navigate toward the next checkpoint using angle calculations.

        Args:
            state: Game state with checkpoint and position data

        Returns:
            BotActions with navigation decisions
        """

        # ============================================================
        # STEP 1: Get Target Checkpoint
        # ============================================================

        # All checkpoints in the stage
        checkpoints = state.track.checkpoints

        # Index of the next checkpoint we need to reach
        next_checkpoint_index = state.track.next_checkpoint

        # Check if we've finished (no more checkpoints)
        if next_checkpoint_index >= len(checkpoints):
            # Keep accelerating toward finish line
            return BotActions(accelerate=True, brake=False)

        # Get the (x, y) position of next checkpoint
        target_position = checkpoints[next_checkpoint_index]


        # ============================================================
        # STEP 2: Calculate Angle to Target
        # ============================================================

        # Our current position
        my_position = state.car.position  # (x, y)
        my_x = my_position[0]
        my_y = my_position[1]

        # Target checkpoint position
        target_x = target_position[0]
        target_y = target_position[1]

        # Calculate vector from us to target
        dx = target_x - my_x  # Change in X
        dy = target_y - my_y  # Change in Y

        # Calculate angle to target using arctangent
        # atan2 gives us the angle in radians from -π to +π
        # 0 radians = pointing right
        # π/2 radians = pointing up
        target_angle = math.atan2(dy, dx)


        # ============================================================
        # STEP 3: Calculate Heading Error
        # ============================================================

        # Which direction are we currently facing?
        my_heading = state.car.heading

        # Calculate the difference between where we're facing
        # and where we want to go
        angle_difference = target_angle - my_heading

        # Normalize the angle to range [-π, +π]
        # This handles the wrap-around at -180°/+180°
        while angle_difference > math.pi:
            angle_difference = angle_difference - (2 * math.pi)
        while angle_difference < -math.pi:
            angle_difference = angle_difference + (2 * math.pi)

        # Now angle_difference tells us:
        # - Positive value = target is to our left
        # - Negative value = target is to our right
        # - Close to zero = we're pointing at target


        # ============================================================
        # STEP 4: Make Steering Decisions
        # ============================================================

        # Determine if we need to turn (outside deadzone?)
        need_to_turn_left = angle_difference > self.steering_threshold
        need_to_turn_right = angle_difference < -self.steering_threshold

        # Is this a sharp turn?
        sharp_turn = abs(angle_difference) > self.sharp_turn_threshold


        # ============================================================
        # STEP 5: Make Speed Decisions
        # ============================================================

        # Brake for sharp turns to avoid overshooting
        should_brake = sharp_turn

        # Accelerate when not braking
        should_accelerate = not should_brake

        # Use nitro when:
        # 1. We have nitro available
        # 2. We're pointing roughly at the target (small angle error)
        # 3. We're not going too slow
        should_use_nitro = (
            state.car.nitro_charges > 0
            and abs(angle_difference) < self.nitro_angle_threshold
            and state.car.speed > 60
        )


        # ============================================================
        # STEP 6: Return Actions
        # ============================================================

        return BotActions(
            accelerate=should_accelerate,
            brake=should_brake,
            turn_left=need_to_turn_left,
            turn_right=need_to_turn_right,
            use_nitro=should_use_nitro
        )


    # ================================================================
    # Helper Methods
    # ================================================================

    def calculate_distance_to_point(self, my_pos, target_pos):
        """
        Calculate Euclidean distance between two points.

        Args:
            my_pos: (x, y) tuple of current position
            target_pos: (x, y) tuple of target position

        Returns:
            float: Distance in units
        """
        dx = target_pos[0] - my_pos[0]
        dy = target_pos[1] - my_pos[1]
        return math.sqrt(dx * dx + dy * dy)


    def normalize_angle(self, angle):
        """
        Normalize angle to range [-π, +π].

        Args:
            angle: Angle in radians

        Returns:
            float: Normalized angle in range [-π, +π]
        """
        while angle > math.pi:
            angle = angle - (2 * math.pi)
        while angle < -math.pi:
            angle = angle + (2 * math.pi)
        return angle


    # ================================================================
    # Event Handlers
    # ================================================================

    def on_checkpoint(self, checkpoint_index, split_time):
        """
        Called when passing a checkpoint.

        Args:
            checkpoint_index: Checkpoint number (0, 1, 2, ...)
            split_time: Time since race start
        """
        # You could use this to track performance
        # Example: Save split times in self.memory for analysis
        pass


    def on_finish(self, finish_time, final_position):
        """
        Called when crossing the finish line.

        Args:
            finish_time: Total time in seconds
            final_position: Final position (1st, 2nd, etc.)
        """
        pass


# ====================================================================
# Tips for Improving This Bot:
# ====================================================================
#
# 1. LOOK AHEAD TO NEXT CHECKPOINT
#    - Instead of targeting just the next checkpoint, look at the
#      checkpoint after that too
#    - This helps you take better racing lines through corners
#    - Example:
#      if next_checkpoint_index + 1 < len(checkpoints):
#          upcoming_checkpoint = checkpoints[next_checkpoint_index + 1]
#          # Adjust steering to prepare for upcoming turn
#
# 2. DYNAMIC BRAKING DISTANCE
#    - Brake earlier when approaching at high speed
#    - Calculate distance to checkpoint and adjust braking
#    - Example:
#      distance_to_cp = self.calculate_distance_to_point(
#          state.car.position, target_position
#      )
#      should_brake = (
#          sharp_turn or
#          (distance_to_cp < 50 and state.car.speed > 80)
#      )
#
# 3. CORNER CUTTING
#    - Use raycasts to detect when you can cut corners
#    - Aim for inside of turns when safe
#    - Example:
#      if sharp_turn and state.rays[0].distance > 100:
#          # Lots of clearance - can cut corner
#          angle_difference *= 0.7  # Less aggressive turn
#
# 4. VELOCITY-BASED STEERING
#    - Consider your velocity direction, not just position
#    - This makes steering smoother and more predictive
#    - Example:
#      velocity_angle = math.atan2(state.car.velocity[1], state.car.velocity[0])
#      # Use velocity_angle instead of my_heading for smoother control
#
# 5. SURFACE ADAPTATION
#    - Combine with surface awareness
#    - Adjust braking threshold based on surface grip
#    - Example:
#      if state.car.current_surface in ["ice", "gravel"]:
#          self.sharp_turn_threshold = 0.3  # Brake earlier on slippery surfaces
#
# 6. OPPONENT AVOIDANCE
#    - Check if opponents are near your target line
#    - Adjust target position to avoid collisions
#    - Example:
#      for opponent in state.opponents:
#          if opponent.distance < 30:
#              # Opponent nearby - slightly adjust target
#              target_x += 10 if opponent.relative_angle > 0 else -10
#
# 7. TRACK BOUNDARY AWARENESS
#    - Use state.track.distance_to_boundary_left/right
#    - Avoid aiming for checkpoints that would take you off track
#    - Example:
#      if state.track.distance_to_boundary_left < 20:
#          angle_difference -= 0.1  # Steer away from left boundary
#
# ====================================================================
#
# MATH REFERENCE:
# ====================================================================
#
# Useful math functions (all from math module):
#
# math.atan2(y, x)    - Calculate angle from origin to point (x, y)
# math.sqrt(x)        - Square root
# math.sin(angle)     - Sine of angle (radians)
# math.cos(angle)     - Cosine of angle (radians)
# math.degrees(rad)   - Convert radians to degrees
# math.radians(deg)   - Convert degrees to radians
# math.pi             - The constant π (3.14159...)
#
# Angle conventions:
# - 0 radians = pointing right (positive X direction)
# - π/2 radians (90°) = pointing up (positive Y direction)
# - π radians (180°) = pointing left (negative X direction)
# - -π/2 radians (-90°) = pointing down (negative Y direction)
#
# ====================================================================
