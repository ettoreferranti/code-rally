"""
Simple Follower Bot - Template for Beginners

This bot uses raycasts (vision sensors) to follow the track.
It's the simplest racing strategy: avoid obstacles and stay on track.

Learning Goals:
- Understanding raycasts (vision sensors)
- Basic steering logic
- Speed control based on obstacles ahead

Difficulty: ★☆☆☆☆ (Beginner)
"""


class SimpleFollower(GuardedBotBase):
    """
    A beginner-friendly bot that uses raycasts to navigate the track.

    Strategy:
    1. Accelerate when the path ahead is clear
    2. Brake when approaching obstacles
    3. Steer away from track boundaries
    """

    def __init__(self):
        """Initialize the bot. Called once when the bot is loaded."""
        self.name = "Simple Follower"

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
        # STEP 2: Make Decisions Based on Sensors
        # ============================================================

        # Check if there's clearance ahead
        # If the front ray shows >30 units, the path is clear
        front_clear = front_ray.distance > 30

        # Check if left side has clearance
        left_clear = left_ray.distance > 50

        # Check if right side has clearance
        right_clear = right_ray.distance > 50


        # ============================================================
        # STEP 3: Decide Actions
        # ============================================================

        # ACCELERATION: Accelerate when path ahead is clear
        should_accelerate = front_clear

        # BRAKING: Brake when getting too close to obstacles
        should_brake = not front_clear

        # STEERING: Turn away from obstacles
        # If left side is blocked but right is clear, turn right
        # If right side is blocked but left is clear, turn left
        should_turn_left = (not left_clear) and right_clear
        should_turn_right = (not right_clear) and left_clear


        # ============================================================
        # STEP 4: Return Actions
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
