#!/usr/bin/env python
"""
Quick test script to verify template bots load and execute correctly.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(__file__))

from app.bot_runtime.templates import get_template_list, get_template_code
from app.core.bot_manager import BotManager
from app.bot_runtime.types import BotGameState, BotCarState, BotTrackState, BotRaycast, BotRaceState


def create_test_state():
    """Create a minimal test game state."""
    return BotGameState(
        car=BotCarState(
            position=(100.0, 100.0),
            heading=0.0,
            speed=50.0,
            velocity=(50.0, 0.0),
            angular_velocity=0.0,
            health=100.0,
            nitro_charges=3,
            nitro_active=False,
            current_surface="asphalt",
            off_track=False
        ),
        track=BotTrackState(
            checkpoints=[(200.0, 100.0), (300.0, 200.0)],
            next_checkpoint=0,
            distance_to_boundary_left=30.0,
            distance_to_boundary_right=30.0,
            upcoming_surface="asphalt",
            upcoming_turn="straight",
            turn_sharpness=0.0
        ),
        rays=[
            BotRaycast(distance=100.0, hit_type=None),  # forward
            BotRaycast(distance=80.0, hit_type=None),   # forward-left 22°
            BotRaycast(distance=60.0, hit_type=None),   # forward-left 45°
            BotRaycast(distance=50.0, hit_type=None),   # left 90°
            BotRaycast(distance=60.0, hit_type=None),   # forward-right 45°
            BotRaycast(distance=80.0, hit_type=None),   # forward-right 22°
            BotRaycast(distance=50.0, hit_type=None),   # right 90°
        ],
        opponents=[],
        race=BotRaceState(
            current_checkpoint=0,
            total_checkpoints=2,
            position=1,
            total_cars=1,
            elapsed_time=10.0,
            distance_to_finish=200.0
        )
    )


def test_template(template_id: str):
    """Test loading and executing a template bot."""
    print(f"\n{'='*60}")
    print(f"Testing template: {template_id}")
    print(f"{'='*60}")

    try:
        # Get template code
        code = get_template_code(template_id)
        print(f"✓ Template code loaded ({len(code)} characters)")

        # Load bot in sandbox
        bot_class_name = {
            "simple_follower": "SimpleFollower",
            "surface_aware": "SurfaceAwareRacer",
            "checkpoint_navigator": "CheckpointNavigator",
            "aggressive_racer": "AggressiveRacer"
        }.get(template_id)

        # Use BotManager to load bot
        bot_manager = BotManager()
        bot_instance = bot_manager.load_bot(code, bot_class_name)
        print(f"✓ Bot loaded in sandbox: {bot_instance.name}")

        # Create test state
        state = create_test_state()

        # Call on_tick
        actions = bot_instance.on_tick(state)
        print(f"✓ on_tick() executed successfully")
        print(f"  Actions: {actions}")

        # Test event handlers
        bot_instance.on_checkpoint(0, 5.0)
        print(f"✓ on_checkpoint() executed")

        bot_instance.on_finish(15.0, 1)
        print(f"✓ on_finish() executed")

        print(f"\n✅ Template '{template_id}' passed all tests!")
        return True

    except Exception as e:
        print(f"\n❌ Template '{template_id}' failed:")
        print(f"  Error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run tests on all templates."""
    print("\n" + "="*60)
    print("TESTING BOT TEMPLATES")
    print("="*60)

    templates = get_template_list()
    print(f"\nFound {len(templates)} templates")

    results = {}
    for template in templates:
        template_id = template["id"]
        results[template_id] = test_template(template_id)

    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for template_id, success in results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} - {template_id}")

    print(f"\nTotal: {passed}/{total} passed")

    if passed == total:
        print("\n🎉 All templates working correctly!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} template(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
