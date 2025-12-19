"""
Base bot class defining the bot API interface.

All user bots should inherit from BaseBot or implement its interface.
This class serves as documentation and a template for bot development.
"""

from typing import Optional
from app.bot_runtime.types import BotGameState, BotActions, CollisionEvent


class BaseBot:
    """
    Base class for all racing bots.

    User bots should inherit from this class and override the callback methods.

    Example:
        class MyBot(BaseBot):
            def __init__(self):
                super().__init__()
                self.name = "My Racing Bot"

            def on_tick(self, state: BotGameState) -> BotActions:
                # Implement racing logic here
                return BotActions(accelerate=True)
    """

    def __init__(self):
        """
        Initialize the bot.

        Called once when the bot is loaded. Use this to:
        - Set the bot's name
        - Initialize instance variables
        - Load persistent memory (if any)
        """
        self.name: str = "Unnamed Bot"

        # Persistent memory across races (automatically saved/loaded)
        # This is managed by the bot runtime system
        if not hasattr(self, 'memory'):
            self.memory: dict = {}

    def on_tick(self, state: BotGameState) -> BotActions:
        """
        Called every game tick (~20 times per second).

        This is the main decision-making method where your bot chooses
        what actions to perform based on sensor data.

        Args:
            state: Complete game state with all sensor data

        Returns:
            BotActions object with desired actions

        Example:
            def on_tick(self, state):
                # Simple wall-following logic
                left_dist = state.rays[2].distance
                right_dist = state.rays[4].distance

                return BotActions(
                    accelerate=True,
                    turn_left=right_dist < left_dist,
                    turn_right=left_dist < right_dist
                )
        """
        # Default: no input (car will coast)
        return BotActions()

    def on_collision(self, event: CollisionEvent) -> None:
        """
        Called when your car collides with something.

        Use this to react to collisions or track collision patterns.

        Args:
            event: Collision event data

        Example:
            def on_collision(self, event):
                if event.other_type == "boundary":
                    # Hit track boundary, might need to steer away
                    pass
                elif event.other_type == "car":
                    # Hit another car
                    opponent_id = event.other_id
                    pass
        """
        pass

    def on_checkpoint(self, checkpoint_index: int, split_time: float) -> None:
        """
        Called when you pass a checkpoint.

        Use this to track progress, update racing lines, or save split times.

        Args:
            checkpoint_index: Index of checkpoint passed (0, 1, 2, ...)
            split_time: Time in seconds since race start

        Example:
            def on_checkpoint(self, checkpoint_index, split_time):
                if checkpoint_index == 0:
                    # First checkpoint, record first split
                    if 'best_first_split' not in self.memory:
                        self.memory['best_first_split'] = split_time
                    elif split_time < self.memory['best_first_split']:
                        self.memory['best_first_split'] = split_time
        """
        pass

    def on_finish(self, finish_time: float, final_position: int) -> None:
        """
        Called when you cross the finish line.

        Use this to update statistics, save best times, or log race results.

        Args:
            finish_time: Total race time in seconds
            final_position: Final race position (1 = 1st place, 2 = 2nd, etc.)

        Example:
            def on_finish(self, finish_time, final_position):
                # Track statistics
                if 'races_completed' not in self.memory:
                    self.memory['races_completed'] = 0
                    self.memory['best_time'] = float('inf')

                self.memory['races_completed'] += 1
                if finish_time < self.memory['best_time']:
                    self.memory['best_time'] = finish_time

                # Learn from performance
                if final_position == 1:
                    self.memory['wins'] = self.memory.get('wins', 0) + 1
        """
        pass

    def on_race_start(self) -> None:
        """
        Called when the race countdown finishes and racing begins.

        Optional callback for initialization logic at race start.

        Example:
            def on_race_start(self):
                # Reset race-specific variables
                self.checkpoints_seen = 0
                self.collision_count = 0
        """
        pass

    def on_race_end(self) -> None:
        """
        Called when the race ends (all players finished or time limit reached).

        Optional callback for cleanup logic at race end.

        Example:
            def on_race_end(self):
                # Log race summary
                if hasattr(self, 'collision_count'):
                    print(f"Had {self.collision_count} collisions this race")
        """
        pass
