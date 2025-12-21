#!/usr/bin/env python3
"""
Demo script to test bot racing.

Runs a simple race with 2 bots to verify the bot lifecycle works.
"""

import asyncio
import time
from app.core.engine import GameEngine, RaceStatus
from app.core.track import TrackGenerator

# Simple bot that goes straight
BOT_1_CODE = """
class StraightBot(BaseBot):
    def on_tick(self, state):
        # Just accelerate straight
        return BotActions(accelerate=True)

    def on_checkpoint(self, checkpoint_index, split_time):
        print(f"[StraightBot] Passed checkpoint {checkpoint_index} at {split_time:.2f}s")

    def on_finish(self, finish_time, final_position):
        print(f"[StraightBot] Finished in position {final_position} with time {finish_time:.2f}s")
"""

# Bot that turns left when it sees obstacles
BOT_2_CODE = """
class SmartBot(BaseBot):
    def on_tick(self, state):
        # Check front raycast
        front_ray = state.rays[0]

        # If obstacle ahead, turn left and brake
        if front_ray.distance < 80:
            return BotActions(accelerate=True, turn_left=True, brake=True)

        # Otherwise accelerate
        return BotActions(accelerate=True)

    def on_checkpoint(self, checkpoint_index, split_time):
        print(f"[SmartBot] Passed checkpoint {checkpoint_index} at {split_time:.2f}s")

    def on_finish(self, finish_time, final_position):
        print(f"[SmartBot] Finished in position {final_position} with time {finish_time:.2f}s")
"""


async def run_bot_race():
    """Run a bot race demonstration."""
    print("=" * 60)
    print("CodeRally Bot Race Demo")
    print("=" * 60)
    print()

    # Generate a track
    print("Generating track...")
    generator = TrackGenerator(seed=42)
    track = generator.generate(difficulty='medium')
    print(f"✓ Track generated with {len(track.checkpoints)} checkpoints")
    print()

    # Create game engine
    print("Initializing game engine...")
    engine = GameEngine(track)
    print("✓ Game engine ready")
    print()

    # Add bot players
    print("Loading bots...")
    try:
        bot1 = engine.add_bot_player("bot1", BOT_1_CODE, "StraightBot")
        print("✓ StraightBot loaded")

        bot2 = engine.add_bot_player("bot2", BOT_2_CODE, "SmartBot")
        print("✓ SmartBot loaded")
    except Exception as e:
        print(f"✗ Failed to load bots: {e}")
        return

    print()
    print(f"Players: {len(engine.state.players)} bots")
    print()

    # Start the race
    print("Starting race countdown...")
    engine.start_race()

    # Wait for countdown
    while engine.state.race_info.status == RaceStatus.COUNTDOWN:
        remaining = engine.state.race_info.countdown_remaining
        print(f"  Countdown: {int(remaining) + 1}...", end='\r')
        engine._tick()
        await asyncio.sleep(0.016)  # ~60Hz

    print("\n🏁 GO!")
    print()

    # Run the race
    last_status_time = time.time()
    tick_count = 0

    while engine.state.race_info.status == RaceStatus.RACING:
        engine._tick()
        tick_count += 1

        # Print status every second
        if time.time() - last_status_time >= 1.0:
            elapsed = time.time() - engine.state.race_info.start_time if engine.state.race_info.start_time else 0
            print(f"  Race time: {elapsed:.1f}s | Tick: {tick_count}")

            for player_id, player in engine.state.players.items():
                status = "FINISHED" if player.is_finished else f"Checkpoint {player.current_checkpoint}/{len(track.checkpoints)}"
                position_str = f"P{player.position}" if player.position else "N/A"
                print(f"    {player_id}: {position_str} | {status}")

            print()
            last_status_time = time.time()

        # Check if all finished or DNF
        all_done = all(p.is_finished or p.dnf for p in engine.state.players.values())
        if all_done:
            break

        await asyncio.sleep(0.016)  # ~60Hz

    print()
    print("=" * 60)
    print("RACE FINISHED!")
    print("=" * 60)
    print()

    # Print final results
    print("Final Results:")
    print("-" * 60)

    # Sort by position
    results = sorted(
        engine.state.players.values(),
        key=lambda p: (p.position if p.position else 999, p.finish_time if p.finish_time else 9999)
    )

    for player in results:
        if player.dnf:
            print(f"  DNF: {player.player_id}")
            if player.bot_error:
                print(f"       Error: {player.bot_error}")
        elif player.is_finished and player.finish_time and engine.state.race_info.start_time:
            race_time = player.finish_time - engine.state.race_info.start_time
            print(f"  P{player.position}: {player.player_id} - {race_time:.2f}s ({player.points} points)")
        else:
            print(f"  ???: {player.player_id} - Did not finish")

    print()
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_bot_race())
