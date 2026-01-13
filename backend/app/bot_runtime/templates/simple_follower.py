"""
Simple Follower Bot - Template for Beginners

This bot combines raycasts for obstacle avoidance with basic checkpoint navigation.
It steers toward checkpoints while avoiding walls and obstacles.

Learning Goals:
- Understanding raycasts (vision sensors)
- Basic checkpoint navigation
- Combining multiple sensors for decisions

Difficulty: ★☆☆☆☆ (Beginner)
"""

import math


class SimpleFollower(GuardedBotBase):
    """
    A beginner-friendly bot that combines checkpoint navigation with obstacle avoidance.

    Strategy:
    1. Calculate direction to next checkpoint
    2. Steer toward checkpoint
    3. Avoid obstacles using raycasts
    4. Brake when approaching turns or obstacles
    """

    def __init__(self):
        """Initialize the bot. Called once when the bot is loaded."""
        self.name = "Simple Follower"
        # Max speed - VERY slow to eliminate drift entirely
        self.max_speed = 60
        # State memory to prevent oscillation
        self.last_turn_left = False
        self.last_turn_right = False

    def on_tick(self, state):
        """
        Called every game tick (~20 times per second).

        This is where your racing logic goes!

        Args:
            state: GameState object containing all sensor data

        Returns:
            BotActions or dict with your controls
        """

        # ============================================================
        # STEP 1: Get Next Checkpoint
        # ============================================================

        checkpoints = state.track.checkpoints
        next_cp_idx = state.track.next_checkpoint

        # Check if we've finished (no more checkpoints)
        if next_cp_idx >= len(checkpoints):
            return BotActions(accelerate=True, brake=False)

        # Get target checkpoint
        target = checkpoints[next_cp_idx]


        # ============================================================
        # STEP 2: Calculate Angle to Checkpoint
        # ============================================================

        # My position and target position
        my_x = state.car.position[0]
        my_y = state.car.position[1]
        target_x = target[0]
        target_y = target[1]

        # Vector from me to target
        dx = target_x - my_x
        dy = target_y - my_y

        # Angle to target (in radians)
        target_angle = math.atan2(dy, dx)

        # How much I need to turn (difference between target angle and my heading)
        angle_diff = target_angle - state.car.heading

        # Normalize angle to [-π, +π]
        while angle_diff > math.pi:
            angle_diff = angle_diff - (2 * math.pi)
        while angle_diff < -math.pi:
            angle_diff = angle_diff + (2 * math.pi)


        # ============================================================
        # STEP 3: Decide Steering (with Hysteresis to prevent oscillation)
        # ============================================================

        # Hysteresis: Don't flip-flop steering every tick
        # If we were turning left, keep turning left unless angle flips significantly right
        # If we were turning right, keep turning right unless angle flips significantly left

        if self.last_turn_left:
            # We were turning left - keep turning left unless angle is now significantly right
            should_turn_left = angle_diff > -0.7  # Keep turning left unless > 40° to right
            should_turn_right = angle_diff < -0.7  # Only turn right if WAY to the right
        elif self.last_turn_right:
            # We were turning right - keep turning right unless angle is now significantly left
            should_turn_left = angle_diff > 0.7  # Only turn left if WAY to the left
            should_turn_right = angle_diff < 0.7  # Keep turning right unless > 40° to left
        else:
            # First decision or going straight - use normal thresholds
            should_turn_left = angle_diff > 0.5
            should_turn_right = angle_diff < -0.5

        # Update memory for next tick
        self.last_turn_left = should_turn_left
        self.last_turn_right = should_turn_right


        # ============================================================
        # STEP 4: Decide Speed (Intentionally Conservative)
        # ============================================================

        # Read front raycast to detect obstacles
        front_ray = state.rays[0]
        current_speed = state.car.speed

        # Strategy: Stay VERY slow to eliminate drift
        # Brake if:
        # 1. Going too fast (> max_speed) OR
        # 2. Obstacle is very close (< 30 units)
        should_brake = (current_speed > self.max_speed) or (front_ray.distance < 30)

        # Accelerate only if slow AND not braking
        should_accelerate = (current_speed < self.max_speed - 5) and (not should_brake)


        # ============================================================
        # STEP 5: Return Actions
        # ============================================================

        return BotActions(
            accelerate=should_accelerate,
            brake=should_brake,
            turn_left=should_turn_left,
            turn_right=should_turn_right,
            use_nitro=False
        )


    # ================================================================
    # Optional Event Handlers
    # ================================================================
    # These methods are called when specific events happen
    # You don't need to implement them, but they can be useful!

    def on_checkpoint(self, checkpoint_index, split_time):
        """
        Called when you pass a checkpoint.

        Args:
            checkpoint_index: Which checkpoint you just passed (0, 1, 2, ...)
            split_time: How many seconds since the race started
        """
        # You could use this to track your progress
        # For example: print(f"Passed checkpoint {checkpoint_index} at {split_time:.2f}s")
        pass

    def on_collision(self, event):
        """
        Called when your car hits something.

        Args:
            event: Collision details
                - event.other_type: What you hit ("car", "boundary", "obstacle")
                - event.impact_speed: How fast the collision was
        """
        # You could use this to adjust your strategy
        # For example, slow down after hitting walls
        pass

    def on_finish(self, finish_time, final_position):
        """
        Called when you cross the finish line.

        Args:
            finish_time: Total time in seconds
            final_position: Your finishing position (1st, 2nd, 3rd, etc.)
        """
        # Celebrate your finish!
        pass


# ====================================================================
# Tips for Improving This Bot:
# ====================================================================
#
# 1. USE MORE RAYCASTS
#    - Try using rays[1] and rays[5] for better peripheral vision
#    - Check rays[3] and rays[6] for side awareness
#
# 2. ADJUST THRESHOLDS
#    - Experiment with different distance thresholds
#    - Current: front_clear = distance > 30
#    - Try: front_clear = distance > 40 or distance > 25
#
# 3. ADD SPEED AWARENESS
#    - Read state.car.speed
#    - Brake earlier when going fast
#    - Example: should_brake = (front_ray.distance < state.car.speed / 2)
#
# 4. COMBINE MULTIPLE RAYS
#    - Average left_ray and rays[1] for better left sensing
#    - Example: left_avg = (rays[1].distance + rays[2].distance) / 2
#
# 5. USE STATE DATA
#    - Check state.car.off_track to detect if you left the track
#    - Check state.car.current_surface to adapt to surface types
#    - Example: Slow down on "gravel" or "ice" surfaces
#
# ====================================================================
