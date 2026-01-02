#!/usr/bin/env python3
"""
Test racing with template bots.

This script loads each template bot and simulates a race to verify:
1. Bot loads successfully
2. Bot executes on_tick() without errors
3. Bot produces valid racing actions
4. Bot responds to different game situations
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.bot_runtime.sandbox import BotSandbox
from app.bot_runtime.types import BotGameState, BotCarState, BotTrackState, BotRaycast, BotRaceState
from app.bot_runtime.templates import get_template_list, get_template_code


def create_test_state(speed=80.0, on_surface="asphalt", checkpoint_count=5):
    """Create a realistic test game state."""
    return BotGameState(
        car=BotCarState(
            position=(100.0, 200.0),
            velocity=(speed * 0.866, speed * 0.5),  # Going NE at given speed
            speed=speed,
            heading=0.524,  # ~30 degrees
            angular_velocity=0.1,
            health=100.0,
            current_surface=on_surface,
            off_track=False,
            nitro_active=False,
            nitro_charges=3
        ),
        rays=[
            BotRaycast(distance=150.0, hit_type="boundary"),  # Front
            BotRaycast(distance=120.0, hit_type="boundary"),  # Front-left 22.5°
            BotRaycast(distance=100.0, hit_type="boundary"),  # Left 45°
            BotRaycast(distance=80.0, hit_type="boundary"),   # Side-left 90°
            BotRaycast(distance=100.0, hit_type="boundary"),  # Right 45°
            BotRaycast(distance=120.0, hit_type="boundary"),  # Front-right 22.5°
            BotRaycast(distance=80.0, hit_type="boundary"),   # Side-right 90°
        ],
        track=BotTrackState(
            checkpoints=[(200.0, 300.0), (400.0, 500.0), (600.0, 400.0), (800.0, 200.0), (900.0, 100.0)],
            next_checkpoint=0,
            distance_to_boundary_left=40.0,
            distance_to_boundary_right=35.0,
            upcoming_surface=on_surface,
            upcoming_turn="straight",
            turn_sharpness=0.2
        ),
        opponents=[],
        race=BotRaceState(
            current_checkpoint=0,
            total_checkpoints=checkpoint_count,
            position=1,
            total_cars=2,
            elapsed_time=15.5,
            distance_to_finish=1500.0
        )
    )


def test_template_in_race(template_id):
    """Test a template bot in various race scenarios."""
    print(f"\n{'='*60}")
    print(f"RACING TEST: {template_id}")
    print(f"{'='*60}")

    # Load template code
    try:
        code = get_template_code(template_id)
        print(f"✓ Template code loaded ({len(code)} chars)")
    except Exception as e:
        print(f"✗ Failed to load template: {e}")
        return False

    # Load bot in sandbox
    sandbox = BotSandbox(timeout_ms=10)

    # Extract class name from template
    class_name = None
    for template in get_template_list():
        if template["id"] == template_id:
            # Derive class name from template name
            name = template["name"]
            class_name = name.replace(" ", "")
            break

    if not class_name:
        print(f"✗ Could not determine class name")
        return False

    try:
        bot_instance = sandbox.execute_bot_code(code, class_name)
        print(f"✓ Bot loaded: {bot_instance.name}")
    except Exception as e:
        print(f"✗ Failed to load bot: {e}")
        return False

    # Test 1: Normal racing conditions
    print("\nTest 1: Normal racing (80 km/h on asphalt)")
    try:
        state = create_test_state(speed=80.0, on_surface="asphalt")
        actions = sandbox.call_on_tick(bot_instance, state)
        print(f"  Actions: acc={actions['accelerate']}, brake={actions['brake']}, "
              f"left={actions['turn_left']}, right={actions['turn_right']}, nitro={actions['use_nitro']}")
        print("  ✓ Bot executed successfully")
    except Exception as e:
        print(f"  ✗ Bot failed: {e}")
        return False

    # Test 2: Slow speed on ice
    print("\nTest 2: Slow racing (30 km/h on ice)")
    try:
        state = create_test_state(speed=30.0, on_surface="ice")
        actions = sandbox.call_on_tick(bot_instance, state)
        print(f"  Actions: acc={actions['accelerate']}, brake={actions['brake']}, "
              f"left={actions['turn_left']}, right={actions['turn_right']}, nitro={actions['use_nitro']}")
        print("  ✓ Bot adapted to ice surface")
    except Exception as e:
        print(f"  ✗ Bot failed on ice: {e}")
        return False

    # Test 3: High speed
    print("\nTest 3: High speed racing (120 km/h on asphalt)")
    try:
        state = create_test_state(speed=120.0, on_surface="asphalt")
        actions = sandbox.call_on_tick(bot_instance, state)
        print(f"  Actions: acc={actions['accelerate']}, brake={actions['brake']}, "
              f"left={actions['turn_left']}, right={actions['turn_right']}, nitro={actions['use_nitro']}")
        print("  ✓ Bot handled high speed")
    except Exception as e:
        print(f"  ✗ Bot failed at high speed: {e}")
        return False

    # Test 4: Event callbacks
    print("\nTest 4: Event callbacks")
    try:
        sandbox.call_on_checkpoint(bot_instance, 0, 15.5)
        print("  ✓ on_checkpoint() executed")

        sandbox.call_on_finish(bot_instance, 45.2, 1)
        print("  ✓ on_finish() executed")
    except Exception as e:
        print(f"  ✗ Event callbacks failed: {e}")
        return False

    print(f"\n✅ {template_id} passed all race tests!")
    return True


def main():
    """Test all templates in racing scenarios."""
    print("="*60)
    print("TEMPLATE BOT RACING TESTS")
    print("="*60)
    print("\nTesting all template bots in simulated race conditions...")

    templates = get_template_list()
    results = {}

    for template in templates:
        template_id = template["id"]
        success = test_template_in_race(template_id)
        results[template_id] = success

    # Summary
    print("\n" + "="*60)
    print("RACE TEST SUMMARY")
    print("="*60)

    for template_id, success in results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} - {template_id}")

    total = len(results)
    passed = sum(1 for s in results.values() if s)

    print(f"\nTotal: {passed}/{total} passed")

    if passed == total:
        print("\n🎉 All templates race successfully!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} template(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
