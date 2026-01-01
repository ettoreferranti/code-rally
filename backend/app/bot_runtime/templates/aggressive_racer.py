"""
Aggressive Racer - Template for Expert Users

This bot combines all available techniques for maximum performance:
- Checkpoint navigation
- Surface adaptation
- Opponent awareness
- Strategic nitro usage
- Risk-taking behavior

Learning Goals:
- Combining multiple strategies
- Opponent tracking and overtaking
- Dynamic risk assessment
- Advanced nitro management

Difficulty: ★★★★☆ (Expert)
"""

import math


class AggressiveRacer(GuardedBotBase):
    """
    An expert-level bot that combines multiple racing strategies.

    Strategy:
    1. Navigate toward checkpoints using math
    2. Adapt speed to surface conditions
    3. Track and overtake opponents
    4. Use nitro aggressively
    5. Take calculated risks for better times
    """

    def __init__(self):
        """Initialize the aggressive racer with configuration."""
        self.name = "Aggressive Racer"

        # Navigation config
        self.steering_sensitivity = 1.5   # How aggressively to steer
        self.lookahead_distance = 80      # How far ahead to look

        # Speed limits by surface (more aggressive than Surface Aware)
        self.max_speeds = {
            "asphalt": 120,  # Push the limits on asphalt
            "wet": 85,       # Moderate caution on wet
            "gravel": 70,    # Controlled on gravel
            "ice": 50        # Careful on ice
        }

        # Risk tolerance (0.0 = safe, 1.0 = reckless)
        self.risk_tolerance = 0.7

        # Opponent tracking
        self.opponent_overtake_distance = 40  # Start overtake maneuver


    def on_tick(self, state):
        """
        Main racing logic combining multiple strategies.

        Args:
            state: Complete game state

        Returns:
            BotActions with aggressive racing decisions
        """

        # ============================================================
        # STEP 1: Analyze Current Situation
        # ============================================================

        situation = self.analyze_situation(state)


        # ============================================================
        # STEP 2: Calculate Navigation
        # ============================================================

        # Get target angle for checkpoint navigation
        target_angle = self.calculate_target_angle(state)

        # Calculate heading error
        angle_error = self.normalize_angle(target_angle - state.car.heading)

        # Adjust for opponents (may modify target slightly)
        angle_error = self.adjust_for_opponents(state, angle_error)


        # ============================================================
        # STEP 3: Determine Speed Strategy
        # ============================================================

        # Get safe max speed for current surface
        surface = state.car.current_surface
        safe_speed = self.max_speeds.get(surface, 60)

        # Increase safe speed based on risk tolerance
        if situation["on_straight"]:
            safe_speed = safe_speed * (1.0 + self.risk_tolerance * 0.3)

        # Check if we should brake
        should_brake = self.should_brake_decision(state, safe_speed, angle_error, situation)


        # ============================================================
        # STEP 4: Strategic Nitro Usage
        # ============================================================

        should_use_nitro = self.should_use_nitro_decision(state, angle_error, situation)


        # ============================================================
        # STEP 5: Steering Decisions
        # ============================================================

        # Calculate steering with sensitivity
        steering_power = angle_error * self.steering_sensitivity

        # Clamp steering to -1.0 to 1.0 range
        steering_power = max(-1.0, min(1.0, steering_power))

        # Convert to binary left/right (threshold = 0.05)
        should_turn_left = steering_power > 0.05
        should_turn_right = steering_power < -0.05


        # ============================================================
        # STEP 6: Return Actions
        # ============================================================

        return BotActions(
            accelerate=not should_brake,
            brake=should_brake,
            turn_left=should_turn_left,
            turn_right=should_turn_right,
            use_nitro=should_use_nitro
        )


    # ================================================================
    # Analysis Methods
    # ================================================================

    def analyze_situation(self, state):
        """
        Analyze current racing situation.

        Returns:
            dict: Situation analysis with various flags
        """
        # Calculate distance to next checkpoint
        if state.track.next_checkpoint < len(state.track.checkpoints):
            target_pos = state.track.checkpoints[state.track.next_checkpoint]
            distance_to_cp = self.calculate_distance(state.car.position, target_pos)
        else:
            distance_to_cp = float('inf')

        return {
            "speed": state.car.speed,
            "surface": state.car.current_surface,
            "off_track": state.car.off_track,
            "on_straight": abs(state.car.angular_velocity) < 0.1,
            "distance_to_checkpoint": distance_to_cp,
            "opponents_nearby": len(state.opponents) > 0,
            "has_nitro": state.car.nitro_charges > 0,
            "front_clear": state.rays[0].distance > 50
        }


    def calculate_target_angle(self, state):
        """
        Calculate angle to target checkpoint.

        Returns:
            float: Target angle in radians
        """
        checkpoints = state.track.checkpoints
        next_idx = state.track.next_checkpoint

        if next_idx >= len(checkpoints):
            # No more checkpoints - keep current heading
            return state.car.heading

        # Get next checkpoint
        target = checkpoints[next_idx]

        # Calculate angle to target
        my_pos = state.car.position
        dx = target[0] - my_pos[0]
        dy = target[1] - my_pos[1]

        return math.atan2(dy, dx)


    def adjust_for_opponents(self, state, angle_error):
        """
        Adjust steering to overtake opponents.

        Args:
            state: Game state
            angle_error: Current angle error

        Returns:
            float: Adjusted angle error
        """
        if not state.opponents:
            return angle_error

        # Find closest opponent ahead
        closest_ahead = None
        mincalculate_distance = float('inf')

        for opponent in state.opponents:
            # Check if opponent is ahead (relative angle small)
            if abs(opponent.relative_angle) < 0.5 and opponent.distance < mincalculate_distance:
                closest_ahead = opponent
                mincalculate_distance = opponent.distance

        # If opponent is close ahead, try to overtake
        if closest_ahead and closest_ahead.distance < self.opponent_overtakecalculate_distance:
            # Adjust steering to go around opponent
            # If opponent is slightly left, steer right to overtake
            # If opponent is slightly right, steer left to overtake
            overtake_adjustment = -opponent.relative_angle * 0.3
            return angle_error + overtake_adjustment

        return angle_error


    def should_brake_decision(self, state, safe_speed, angle_error, situation):
        """
        Determine if we should brake.

        Args:
            state: Game state
            safe_speed: Maximum safe speed for current conditions
            angle_error: Steering angle error
            situation: Situation analysis dict

        Returns:
            bool: True if should brake
        """
        # Brake if going too fast for surface
        if state.car.speed > safe_speed:
            return True

        # Brake for sharp turns
        if abs(angle_error) > 0.6:
            return True

        # Brake if off track
        if situation["off_track"]:
            return True

        # Brake if obstacle very close ahead
        if state.rays[0].distance < 20:
            return True

        # Brake if opponent collision imminent
        for opponent in state.opponents:
            if opponent.distance < 15 and abs(opponent.relative_angle) < 0.3:
                return True

        return False


    def should_use_nitro_decision(self, state, angle_error, situation):
        """
        Determine if we should use nitro boost.

        Args:
            state: Game state
            angle_error: Steering angle error
            situation: Situation analysis dict

        Returns:
            bool: True if should activate nitro
        """
        # Must have nitro available
        if not situation["has_nitro"]:
            return False

        # Don't use while off track
        if situation["off_track"]:
            return False

        # Use on good surfaces when going straight
        good_surfaces = {"asphalt", "wet"}
        if (situation["surface"] in good_surfaces
            and abs(angle_error) < 0.2
            and situation["on_straight"]
            and state.car.speed > 60):
            return True

        # Aggressive: Use to overtake opponents
        if situation["opponents_nearby"] and situation["front_clear"]:
            for opponent in state.opponents:
                # If opponent is close and we're behind, use nitro to pass
                if 20 < opponent.distance < 40 and abs(opponent.relative_angle) < 0.4:
                    return True

        return False


    # ================================================================
    # Utility Methods
    # ================================================================

    def calculate_distance(self, pos1, pos2):
        """Calculate Euclidean distance between two points."""
        dx = pos2[0] - pos1[0]
        dy = pos2[1] - pos1[1]
        return math.sqrt(dx * dx + dy * dy)


    def normalize_angle(self, angle):
        """Normalize angle to [-π, +π] range."""
        while angle > math.pi:
            angle = angle - (2 * math.pi)
        while angle < -math.pi:
            angle = angle + (2 * math.pi)
        return angle


    # ================================================================
    # Event Handlers
    # ================================================================

    def on_collision(self, event):
        """
        React to collisions by temporarily reducing aggression.

        Args:
            event: Collision event
        """
        # Could reduce risk tolerance after crashes
        # self.risk_tolerance = max(0.3, self.risk_tolerance - 0.1)
        pass


    def on_checkpoint(self, checkpoint_index, split_time):
        """
        Track checkpoint times for performance analysis.

        Args:
            checkpoint_index: Checkpoint number
            split_time: Time since race start
        """
        # Could use self.memory to track and improve performance
        # if "split_times" not in self.memory:
        #     self.memory["split_times"] = []
        # self.memory["split_times"].append(split_time)
        pass


    def on_finish(self, finish_time, final_position):
        """
        Called when crossing finish line.

        Args:
            finish_time: Total time in seconds
            final_position: Final position (1st, 2nd, etc.)
        """
        pass


# ====================================================================
# Tips for Improving This Bot:
# ====================================================================
#
# 1. MACHINE LEARNING APPROACH
#    - Use self.memory to track what works across races
#    - Adjust risk_tolerance based on success rate
#    - Learn optimal speeds for each surface
#    - Example:
#      if "crash_count" in self.memory:
#          self.risk_tolerance = max(0.3, 1.0 - self.memory["crash_count"] * 0.1)
#
# 2. ADVANCED LOOKAHEAD
#    - Look at multiple checkpoints ahead
#    - Plan racing line through multiple corners
#    - Anticipate surface changes
#    - Example:
#      if next_idx + 2 < len(checkpoints):
#          future_cp = checkpoints[next_idx + 2]
#          # Adjust current steering to prepare for future turn
#
# 3. DYNAMIC RISK ADJUSTMENT
#    - Increase risk when behind in race
#    - Decrease risk when in the lead
#    - Example:
#      if state.race.position > 3:
#          self.risk_tolerance = 0.9  # More aggressive when behind
#      elif state.race.position == 1:
#          self.risk_tolerance = 0.5  # More conservative when leading
#
# 4. OPPONENT PREDICTION
#    - Track opponent velocity vectors
#    - Predict where they'll be in 1-2 seconds
#    - Plan overtakes more intelligently
#    - Example:
#      predicted_pos = (
#          opponent.position[0] + opponent.velocity[0] * 2.0,
#          opponent.position[1] + opponent.velocity[1] * 2.0
#      )
#
# 5. RACING LINE OPTIMIZATION
#    - Use track boundaries to find optimal path
#    - Late apex cornering technique
#    - Maximize use of track width
#    - Example:
#      # Aim for inside of corner
#      if angle_error > 0:  # Turning left
#          target_x += state.track.distance_to_boundary_right * 0.3
#
# 6. TIRE MANAGEMENT (if implemented)
#    - Track cumulative drift/wear
#    - Reduce aggression when tires degraded
#    - Balance speed vs. tire preservation
#
# 7. FUEL MANAGEMENT (if implemented)
#    - Calculate if you have enough fuel to finish
#    - Adjust strategy based on fuel remaining
#    - Coast when fuel-critical
#
# ====================================================================
