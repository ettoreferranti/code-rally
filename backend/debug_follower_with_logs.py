"""
Simple Follower Bot - DEBUG VERSION with logging
"""

import math


class SimpleFollower(GuardedBotBase):
    """Debug version of Simple Follower with logging."""

    def __init__(self):
        self.name = "Debug Simple Follower"
        self.steering_threshold = 0.1
        self.tick_count = 0
        self.last_checkpoint_reported = -1

    def on_tick(self, state):
        self.tick_count += 1

        # Log checkpoint info periodically
        if self.tick_count % 20 == 0:  # Every second (20Hz)
            print(f"\n[DEBUG Tick {self.tick_count}]")
            print(f"  Position: ({state.car.position[0]:.1f}, {state.car.position[1]:.1f})")
            print(f"  Speed: {state.car.speed:.1f}")
            print(f"  Next checkpoint index: {state.track.next_checkpoint}")
            print(f"  Total checkpoints: {len(state.track.checkpoints)}")
            if state.track.next_checkpoint < len(state.track.checkpoints):
                target = state.track.checkpoints[state.track.next_checkpoint]
                print(f"  Target checkpoint: ({target[0]:.1f}, {target[1]:.1f})")

        # Get sensor data
        front_ray = state.rays[0]
        left_ray = state.rays[2]
        right_ray = state.rays[4]

        # Get checkpoint navigation
        checkpoints = state.track.checkpoints
        next_cp_idx = state.track.next_checkpoint

        # Check if finished
        if next_cp_idx >= len(checkpoints):
            print(f"[DEBUG] FINISHED! next_cp_idx={next_cp_idx} >= len(checkpoints)={len(checkpoints)}")
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
        distance_to_target = math.sqrt(dx * dx + dy * dy)

        # Log when approaching checkpoint
        if distance_to_target < 100 and self.tick_count % 10 == 0:
            print(f"[DEBUG] Approaching checkpoint {next_cp_idx}, distance: {distance_to_target:.1f}")

        target_angle = math.atan2(dy, dx)
        angle_diff = target_angle - state.car.heading

        # Normalize angle
        while angle_diff > math.pi:
            angle_diff -= 2 * math.pi
        while angle_diff < -math.pi:
            angle_diff += 2 * math.pi

        # Steering decisions
        should_turn_left = angle_diff > self.steering_threshold
        should_turn_right = angle_diff < -self.steering_threshold

        # Emergency obstacle avoidance
        if front_ray.distance < 30:
            if left_ray.distance > right_ray.distance:
                should_turn_left = True
                should_turn_right = False
            else:
                should_turn_left = False
                should_turn_right = True

        # Speed decisions
        should_brake = front_ray.distance < 30 or abs(angle_diff) > 0.8
        should_accelerate = not should_brake

        return BotActions(
            accelerate=should_accelerate,
            brake=should_brake,
            turn_left=should_turn_left,
            turn_right=should_turn_right,
            use_nitro=False
        )

    def on_checkpoint(self, checkpoint_index, split_time):
        print(f"\n[DEBUG] ✓ PASSED CHECKPOINT {checkpoint_index} at {split_time:.2f}s")
        self.last_checkpoint_reported = checkpoint_index
