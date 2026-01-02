#!/usr/bin/env python3
"""
Test bots in a turning scenario - checkpoint is to the left.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.bot_runtime.sandbox import BotSandbox
from app.bot_runtime.types import BotGameState, BotCarState, BotTrackState, BotRaycast, BotRaceState
from app.bot_runtime.templates import get_template_code, get_template_list
import math


def test_turn_scenario(template_id):
    """Test bot when it needs to turn LEFT to reach checkpoint."""
    print(f"\n{'='*70}")
    print(f"Testing TURN: {template_id}")
    print(f"{'='*70}")

    # Load bot
    code = get_template_code(template_id)
    templates = get_template_list()
    template = next((t for t in templates if t["id"] == template_id), None)
    class_name = template["name"].replace(" ", "")

    sandbox = BotSandbox(timeout_ms=10)
    bot = sandbox.execute_bot_code(code, class_name)

    # Create state where checkpoint is 90° to the LEFT
    state = BotGameState(
        car=BotCarState(
            position=(100.0, 100.0),
            velocity=(50.0, 0.0),  # Moving EAST at 50 units/s
            speed=50.0,
            heading=0.0,  # Facing EAST (0°)
            angular_velocity=0.0,
            health=100.0,
            nitro_charges=3,
            nitro_active=False,
            current_surface="asphalt",
            off_track=False
        ),
        rays=[
            BotRaycast(distance=200.0, hit_type=None),  # Front - clear
            BotRaycast(distance=180.0, hit_type=None),
            BotRaycast(distance=160.0, hit_type=None),  # Left 45° - clear
            BotRaycast(distance=100.0, hit_type="boundary"),  # Left 90°
            BotRaycast(distance=160.0, hit_type=None),
            BotRaycast(distance=180.0, hit_type=None),
            BotRaycast(distance=100.0, hit_type="boundary"),
        ],
        track=BotTrackState(
            checkpoints=[
                (100.0, 500.0),   # Checkpoint is NORTH (90° left turn needed)
                (500.0, 500.0),
            ],
            next_checkpoint=0,
            distance_to_boundary_left=50.0,
            distance_to_boundary_right=50.0,
            upcoming_surface="asphalt",
            upcoming_turn="left",
            turn_sharpness=0.8
        ),
        opponents=[],
        race=BotRaceState(
            current_checkpoint=0,
            total_checkpoints=2,
            position=1,
            total_cars=1,
            elapsed_time=5.0,
            distance_to_finish=800.0
        )
    )

    cp = state.track.checkpoints[0]
    my_pos = state.car.position
    dx = cp[0] - my_pos[0]
    dy = cp[1] - my_pos[1]
    target_angle = math.atan2(dy, dx)
    angle_diff = target_angle - state.car.heading

    while angle_diff > math.pi:
        angle_diff -= 2 * math.pi
    while angle_diff < -math.pi:
        angle_diff += 2 * math.pi

    print(f"   Car heading: {math.degrees(state.car.heading):.1f}° (facing EAST)")
    print(f"   Checkpoint at: ({cp[0]:.1f}, {cp[1]:.1f}) - NORTH of car")
    print(f"   Target angle: {math.degrees(target_angle):.1f}°")
    print(f"   Angle error: {math.degrees(angle_diff):.1f}° ({'LEFT' if angle_diff > 0 else 'RIGHT'})")
    print(f"   Speed: {state.car.speed:.1f} units/s")

    # Execute bot
    actions = sandbox.call_on_tick(bot, state)

    print(f"\n   BOT ACTIONS:")
    print(f"      Turn Left:  {'⬅️  YES' if actions['turn_left'] else '   NO'} (should be YES)")
    print(f"      Turn Right: {'➡️  YES' if actions['turn_right'] else '   NO'} (should be NO)")
    print(f"      Accelerate: {'✅ YES' if actions['accelerate'] else '❌ NO'}")
    print(f"      Brake:      {'🛑 YES' if actions['brake'] else '   NO'}")

    # Check if correct
    if actions['turn_left'] and not actions['turn_right']:
        print(f"   ✅ CORRECT: Bot is turning left!")
        return True
    elif not actions['turn_left'] and not actions['turn_right']:
        print(f"   ❌ ERROR: Bot is NOT turning (will miss checkpoint)!")
        return False
    elif actions['turn_right']:
        print(f"   ❌ ERROR: Bot is turning RIGHT instead of LEFT!")
        return False


print("="*70)
print("BOT TURN TEST - Checkpoint 90° to the LEFT")
print("="*70)

templates = get_template_list()
results = {}

for template in templates:
    try:
        success = test_turn_scenario(template["id"])
        results[template["id"]] = success
    except Exception as e:
        print(f"   ❌ CRASHED: {e}")
        import traceback
        traceback.print_exc()
        results[template["id"]] = False

print(f"\n{'='*70}")
print("SUMMARY")
print(f"{'='*70}")
for template_id, success in results.items():
    status = "✅ PASS" if success else "❌ FAIL"
    print(f"{status} - {template_id}")
