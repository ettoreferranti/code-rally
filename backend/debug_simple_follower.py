"""
Debug script to test simple follower bot checkpoint navigation.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app.core.engine import GameEngine
from app.core.track import TrackGenerator
import time

def test_simple_follower():
    """Test the simple follower template to debug checkpoint issue."""
    print("=== Testing Simple Follower Bot ===\n")

    # Create game engine
    engine = GameEngine()

    # Generate a simple track
    generator = TrackGenerator(seed=42)
    track = generator.generate(difficulty="easy")
    print(f"Track has {len(track.checkpoints)} checkpoints")

    # Load simple follower template
    with open('app/bot_runtime/templates/simple_follower.py', 'r') as f:
        bot_code = f.read()

    # Create a bot player
    player_id = engine.create_bot_player("TestBot", bot_code, "SimpleFollower")
    print(f"Created bot player: {player_id}\n")

    # Start the race
    engine.start_race(track)
    print("Race started\n")

    # Run simulation and track checkpoint progress
    max_ticks = 2000  # ~33 seconds at 60Hz
    last_checkpoint = -1

    for tick in range(max_ticks):
        state = engine.tick(tick / 60.0)  # Pass time in seconds

        if state:
            player = state['players'][player_id]
            current_cp = player['current_checkpoint']

            # Print when checkpoint changes
            if current_cp != last_checkpoint:
                print(f"Tick {tick}: Checkpoint updated: {last_checkpoint} → {current_cp}")
                print(f"  Position: ({player['position'][0]:.1f}, {player['position'][1]:.1f})")
                print(f"  Speed: {player['speed']:.1f}")
                print(f"  Total checkpoints: {len(track.checkpoints)}")

                # Check if bot is finished
                if current_cp >= len(track.checkpoints):
                    print(f"\n✓ Bot finished! Passed all {len(track.checkpoints)} checkpoints")
                    break

                last_checkpoint = current_cp

            # Stop if bot hasn't moved in a while (stuck)
            if tick > 500 and current_cp == 1:
                print(f"\n✗ Bot appears stuck at checkpoint {current_cp} after {tick} ticks")
                print(f"  Final position: ({player['position'][0]:.1f}, {player['position'][1]:.1f})")
                print(f"  Speed: {player['speed']:.1f}")
                print(f"  Finished: {player['is_finished']}")
                break

            # Check if finished
            if player['is_finished']:
                print(f"\n✓ Bot finished at tick {tick}")
                print(f"  Final checkpoint: {current_cp}/{len(track.checkpoints)}")
                break
    else:
        # Max ticks reached
        player = state['players'][player_id]
        print(f"\n⏱ Max ticks reached ({max_ticks})")
        print(f"  Final checkpoint: {player['current_checkpoint']}/{len(track.checkpoints)}")
        print(f"  Position: ({player['position'][0]:.1f}, {player['position'][1]:.1f})")

if __name__ == "__main__":
    test_simple_follower()
