#!/usr/bin/env python3
"""
Live bot debugging script.

This script simulates a simple race scenario and shows exactly what
each template bot sees and decides to do.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.bot_runtime.sandbox import BotSandbox
from app.bot_runtime.types import BotGameState, BotCarState, BotTrackState, BotRaycast, BotRaceState
from app.bot_runtime.templates import get_template_code, get_template_list
import math


def create_realistic_race_state():
    """Create a race state that matches what bots actually see in game."""
    return BotGameState(
        car=BotCarState(
            position=(100.0, 100.0),  # Starting position
            velocity=(0.0, 0.0),  # Starting from rest
            speed=0.0,
            heading=0.0,  # Pointing right (0 radians)
            angular_velocity=0.0,
            health=100.0,
            nitro_charges=3,
            nitro_active=False,
            current_surface="asphalt",
            off_track=False
        ),
        rays=[
            # Front-facing rays should have good clearance on a straight
            BotRaycast(distance=200.0, hit_type=None),  # 0: Straight ahead - MAX range = clear
            BotRaycast(distance=180.0, hit_type=None),  # 1: 22.5° left
            BotRaycast(distance=160.0, hit_type=None),  # 2: 45° left
            BotRaycast(distance=100.0, hit_type="boundary"),  # 3: 90° left (side)
            BotRaycast(distance=160.0, hit_type=None),  # 4: 45° right
            BotRaycast(distance=180.0, hit_type=None),  # 5: 22.5° right
            BotRaycast(distance=100.0, hit_type="boundary"),  # 6: 90° right (side)
        ],
        track=BotTrackState(
            checkpoints=[
                (500.0, 100.0),   # First checkpoint - straight ahead
                (900.0, 300.0),   # Second checkpoint
                (700.0, 600.0),   # Third checkpoint
            ],
            next_checkpoint=0,
            distance_to_boundary_left=50.0,
            distance_to_boundary_right=50.0,
            upcoming_surface="asphalt",
            upcoming_turn="straight",
            turn_sharpness=0.1
        ),
        opponents=[],
        race=BotRaceState(
            current_checkpoint=0,
            total_checkpoints=3,
            position=1,
            total_cars=1,
            elapsed_time=0.0,
            distance_to_finish=1200.0
        )
    )


def test_bot_decision(template_id):
    """Test what a template bot decides to do in a simple scenario."""
    print(f"\n{'='*70}")
    print(f"Testing: {template_id}")
    print(f"{'='*70}")

    # Load template
    try:
        code = get_template_code(template_id)
        templates = get_template_list()
        template = next((t for t in templates if t["id"] == template_id), None)
        class_name = template["name"].replace(" ", "") if template else None

        if not class_name:
            print(f"❌ Could not find template")
            return

    except Exception as e:
        print(f"❌ Failed to load template: {e}")
        return

    # Load bot
    sandbox = BotSandbox(timeout_ms=10)
    try:
        bot = sandbox.execute_bot_code(code, class_name)
        print(f"✅ Bot loaded: {bot.name}")
    except Exception as e:
        print(f"❌ Failed to instantiate bot: {e}")
        return

    # Create race state
    state = create_realistic_race_state()

    print("\n📊 RACE SITUATION:")
    print(f"   Car position: ({state.car.position[0]:.1f}, {state.car.position[1]:.1f})")
    print(f"   Car heading: {math.degrees(state.car.heading):.1f}° (0° = right/east)")
    print(f"   Car speed: {state.car.speed:.1f} units/s")
    print(f"   Next checkpoint: #{state.track.next_checkpoint} at ({state.track.checkpoints[0][0]:.1f}, {state.track.checkpoints[0][1]:.1f})")

    # Calculate angle to checkpoint
    cp = state.track.checkpoints[0]
    my_pos = state.car.position
    dx = cp[0] - my_pos[0]
    dy = cp[1] - my_pos[1]
    target_angle = math.atan2(dy, dx)
    angle_diff = target_angle - state.car.heading

    # Normalize angle
    while angle_diff > math.pi:
        angle_diff -= 2 * math.pi
    while angle_diff < -math.pi:
        angle_diff += 2 * math.pi

    print(f"   Angle to checkpoint: {math.degrees(target_angle):.1f}°")
    print(f"   Angle error: {math.degrees(angle_diff):.1f}° ({'LEFT' if angle_diff > 0 else 'RIGHT' if angle_diff < 0 else 'STRAIGHT'})")

    print(f"\n   Raycasts:")
    ray_names = ["Front (0°)", "Front-Left (22.5°)", "Left (45°)", "Side-Left (90°)",
                 "Right (45°)", "Front-Right (22.5°)", "Side-Right (90°)"]
    for i, (ray, name) in enumerate(zip(state.rays, ray_names)):
        hit_str = f" - {ray.hit_type}" if ray.hit_type else " - CLEAR"
        print(f"      {name}: {ray.distance:.1f}{hit_str}")

    # Execute bot
    try:
        actions = sandbox.call_on_tick(bot, state)

        print(f"\n🎮 BOT ACTIONS:")
        print(f"   Accelerate: {'✅ YES' if actions['accelerate'] else '❌ NO'}")
        print(f"   Brake:      {'🛑 YES' if actions['brake'] else '   NO'}")
        print(f"   Turn Left:  {'⬅️  YES' if actions['turn_left'] else '   NO'}")
        print(f"   Turn Right: {'➡️  YES' if actions['turn_right'] else '   NO'}")
        print(f"   Use Nitro:  {'⚡ YES' if actions['use_nitro'] else '   NO'}")

        # Analyze decision
        print(f"\n🔍 ANALYSIS:")
        if not actions['accelerate'] and not actions['brake']:
            print(f"   ⚠️  WARNING: Bot is neither accelerating nor braking! It will coast.")
        if actions['turn_left'] and actions['turn_right']:
            print(f"   ⚠️  WARNING: Bot is turning both left AND right!")
        if not actions['turn_left'] and not actions['turn_right']:
            if abs(angle_diff) > 0.1:
                print(f"   ⚠️  WARNING: Bot should turn but isn't! Needs to turn {math.degrees(abs(angle_diff)):.1f}°")
            else:
                print(f"   ✅ Bot is going straight (correct for this scenario)")
        else:
            if actions['turn_left'] and angle_diff > 0:
                print(f"   ✅ Bot is turning left (correct - target is {math.degrees(angle_diff):.1f}° left)")
            elif actions['turn_right'] and angle_diff < 0:
                print(f"   ✅ Bot is turning right (correct - target is {math.degrees(abs(angle_diff)):.1f}° right)")
            elif actions['turn_left'] and angle_diff < 0:
                print(f"   ❌ ERROR: Bot is turning LEFT but should turn RIGHT!")
            elif actions['turn_right'] and angle_diff > 0:
                print(f"   ❌ ERROR: Bot is turning RIGHT but should turn LEFT!")

        return True

    except Exception as e:
        print(f"\n❌ Bot execution failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Test all templates."""
    print("="*70)
    print("BOT LIVE DEBUGGING - Race Start Scenario")
    print("="*70)
    print("\nThis simulates what bots see at the START of a race.")
    print("Car is at (100, 100), facing EAST (0°), speed 0")
    print("First checkpoint is at (500, 100) - 400 units to the EAST")
    print("Front rays show clear path ahead (200 units visible)")

    templates = get_template_list()
    results = {}

    for template in templates:
        success = test_bot_decision(template["id"])
        results[template["id"]] = success

    # Summary
    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")

    for template_id, success in results.items():
        status = "✅ WORKING" if success else "❌ BROKEN"
        print(f"{status} - {template_id}")


if __name__ == "__main__":
    main()
