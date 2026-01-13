"""
Test Bot - Minimal bot for debugging
"""

class TestBot(GuardedBotBase):
    """Minimal test bot that just accelerates."""

    def __init__(self):
        self.name = "Test Bot"

    def on_tick(self, state):
        """Test boolean logic and 'not' operator."""
        # Test 1: Direct boolean assignment (this worked)
        # return BotActions(accelerate=True, brake=False, ...)

        # Test 2: Boolean variables (testing now)
        should_brake = False
        should_accelerate = not should_brake  # Test if 'not' works

        return BotActions(
            accelerate=should_accelerate,
            brake=should_brake,
            turn_left=False,
            turn_right=False,
            use_nitro=False
        )
