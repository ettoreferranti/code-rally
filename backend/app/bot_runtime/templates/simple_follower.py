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
        self.steering_threshold = 0.1  # Don't turn for tiny angle differences

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
        # STEP 1: Read Sensor Data
        # ============================================================

        # Your bot has 7 raycasts (vision sensors) arranged like this:
        #
        #      ray[2]  ray[1]  ray[0]   <- 45°, 22°, 0° (forward)
        #           \    |    /
        #            \   |   /
        # ray[3] ──── YOUR CAR ──── (forward = ray[0])
        #            /   |   \
        #           /    |    \
        #      ray[4]  ray[5]  ray[6]   <- -45°, -22°, 0° (forward)
        #
        # Each ray returns:
        # - distance: How far until hitting something (max 200 units)
        # - hit_type: What it hit ("boundary", "car", "obstacle", or None)

        # Ray 0: Straight ahead
        front_ray = state.rays[0]

        # Ray 2: Forward-left (45 degrees left)
        left_ray = state.rays[2]

        # Ray 4: Forward-right (45 degrees right)
        right_ray = state.rays[4]


        # ============================================================
        # STEP 2: Calculate Direction to Checkpoint
        # ============================================================

        # Get next checkpoint position
        checkpoints = state.track.checkpoints
        next_cp_idx = state.track.next_checkpoint

        # Check if we've finished (no more checkpoints)
        if next_cp_idx >= len(checkpoints):
            # Keep going straight
            return BotActions(accelerate=True, brake=False)

        # Get target checkpoint
        target = checkpoints[next_cp_idx]

        # Calculate angle to target
        my_x = state.car.position[0]
        my_y = state.car.position[1]
        target_x = target[0]
        target_y = target[1]

        dx = target_x - my_x
        dy = target_y - my_y

        # Use atan2 to get angle (in radians) to checkpoint
        target_angle = math.atan2(dy, dx)

        # Calculate how much we need to turn
        angle_diff = target_angle - state.car.heading

        # Normalize angle to [-π, +π]
        while angle_diff > math.pi:
            angle_diff -= 2 * math.pi
        while angle_diff < -math.pi:
            angle_diff += 2 * math.pi


        # ============================================================
        # STEP 3: Decide Steering (toward checkpoint, avoid obstacles)
        # ============================================================

        # Default: steer toward checkpoint
        should_turn_left = angle_diff > self.steering_threshold
        should_turn_right = angle_diff < -self.steering_threshold

        # Override if obstacle is very close (emergency avoidance)
        if front_ray.distance < 30:
            # Obstacle ahead! Turn away from it
            if left_ray.distance > right_ray.distance:
                # More space on left
                should_turn_left = True
                should_turn_right = False
            else:
                # More space on right
                should_turn_left = False
                should_turn_right = True


        # ============================================================
        # STEP 4: Decide Speed
        # ============================================================

        # Brake if obstacle very close OR making sharp turn
        should_brake = front_ray.distance < 30 or abs(angle_diff) > 0.8

        # Accelerate if not braking
        should_accelerate = not should_brake


        # ============================================================
        # STEP 5: Return Actions
        # ============================================================

        # Return a BotActions object (or dictionary) with your decisions
        return BotActions(
            accelerate=should_accelerate,
            brake=should_brake,
            turn_left=should_turn_left,
            turn_right=should_turn_right,
            use_nitro=False  # Not using nitro in this simple bot
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
