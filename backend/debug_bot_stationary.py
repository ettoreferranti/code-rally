#!/usr/bin/env python3
"""
Debug why bots might be stationary (speed = 0, not accelerating).
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.bot_runtime.sandbox import BotSandbox
from app.bot_runtime.types import BotGameState, BotCarState, BotTrackState, BotRaycast, BotRaceState
from app.bot_runtime.templates import get_template_code, get_template_list
import math


def test_stationary_bot(template_id):
    """Test bot when stationary at race start."""
    print(f"\n{'='*70}")
    print(f"Testing STATIONARY: {template_id}")
    print(f"{'='*70}")

    # Load bot
    code = get_template_code(template_id)
    templates = get_template_list()
    template = next((t for t in templates if t["id"] == template_id), None)
    class_name = template["name"].replace(" ", "")

    sandbox = BotSandbox(timeout_ms=10)
    bot = sandbox.execute_bot_code(code, class_name)

    # Create state: car is STATIONARY at start, checkpoint ahead
    state = BotGameState(
        car=BotCarState(
            position=(100.0, 100.0),
            velocity=(0.0, 0.0),  # STOPPED
            speed=0.0,  # ZERO SPEED
            heading=0.0,  # Facing EAST
            angular_velocity=0.0,
            health=100.0,
            nitro_charges=3,
            nitro_active=False,
            current_surface="asphalt",
            off_track=False
        ),
        rays=[
            BotRaycast(distance=200.0, hit_type=None),  # Clear ahead
            BotRaycast(distance=200.0, hit_type=None),
            BotRaycast(distance=200.0, hit_type=None),
            BotRaycast(distance=100.0, hit_type="boundary"),
            BotRaycast(distance=200.0, hit_type=None),
            BotRaycast(distance=200.0, hit_type=None),
            BotRaycast(distance=100.0, hit_type="boundary"),
        ],
        track=BotTrackState(
            checkpoints=[
                (500.0, 100.0),   # Straight ahead - easy target
                (900.0, 100.0),
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
            total_checkpoints=2,
            position=1,
            total_cars=1,
            elapsed_time=0.5,
            distance_to_finish=800.0
        )
    )

    print(f"   Car: STATIONARY at (100, 100), heading EAST (0°)")
    print(f"   Checkpoint: (500, 100) - 400 units straight ahead")
    print(f"   Surface: asphalt")
    print(f"   Front ray: {state.rays[0].distance:.1f} (clear)")

    # Execute bot
    try:
        actions = sandbox.call_on_tick(bot, state)

        print(f"\n   BOT ACTIONS:")
        print(f"      Accelerate: {'✅ YES' if actions['accelerate'] else '❌ NO'} (SHOULD BE YES!)")
        print(f"      Brake:      {'🛑 YES' if actions['brake'] else '   NO'} (should be NO)")
        print(f"      Turn Left:  {'⬅️  YES' if actions['turn_left'] else '   NO'}")
        print(f"      Turn Right: {'➡️  YES' if actions['turn_right'] else '   NO'}")
        print(f"      Use Nitro:  {'⚡ YES' if actions['use_nitro'] else '   NO'}")

        # Diagnose
        if not actions['accelerate']:
            print(f"\n   ❌ PROBLEM: Bot is NOT accelerating!")
            print(f"      The bot will stay at speed 0 forever.")
            return False
        elif actions['brake']:
            print(f"\n   ❌ PROBLEM: Bot is braking while stopped!")
            return False
        else:
            print(f"\n   ✅ GOOD: Bot will accelerate and start moving")
            return True

    except Exception as e:
        print(f"\n   ❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


print("="*70)
print("BOT STATIONARY TEST - Why aren't they moving?")
print("="*70)

templates = get_template_list()
results = {}

for template in templates:
    try:
        success = test_stationary_bot(template["id"])
        results[template["id"]] = success
    except Exception as e:
        print(f"   ❌ CRASHED: {e}")
        results[template["id"]] = False

print(f"\n{'='*70}")
print("SUMMARY")
print(f"{'='*70}")
for template_id, success in results.items():
    status = "✅ WILL MOVE" if success else "❌ WON'T MOVE"
    print(f"{status} - {template_id}")
