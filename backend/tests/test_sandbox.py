"""
Security tests for RestrictedPython bot sandbox.

These tests verify that user bot code cannot:
- Access filesystem
- Access network
- Import unauthorized modules
- Use dangerous built-ins
- Run indefinitely (timeout enforcement)
- Use excessive memory

Tests are written FIRST (TDD) to ensure security requirements are met.
"""

import pytest
from app.bot_runtime.sandbox import BotSandbox, SandboxSecurityError, SandboxTimeoutError
from app.bot_runtime.types import BotGameState, BotCarState, BotTrackState, BotRaceState


def create_mock_state():
    """Helper function to create a mock game state for testing."""
    return BotGameState(
        car=BotCarState(
            position=(0, 0), heading=0, speed=0, velocity=(0, 0),
            angular_velocity=0, health=100, nitro_charges=2,
            nitro_active=False, current_surface="asphalt", off_track=False
        ),
        track=BotTrackState(
            checkpoints=[], next_checkpoint=0,
            distance_to_boundary_left=50, distance_to_boundary_right=50,
            upcoming_surface="asphalt", upcoming_turn="straight", turn_sharpness=0
        ),
        rays=[],
        opponents=[],
        race=BotRaceState(
            current_checkpoint=0, total_checkpoints=5, position=1,
            total_cars=1, elapsed_time=0, distance_to_finish=1000
        )
    )


class TestSandboxSecurity:
    """Test that sandbox blocks malicious operations."""

    def test_blocks_file_read_attempt(self):
        """Test that bot cannot read files."""
        malicious_code = """
class MaliciousBot:
    def on_tick(self, state):
        # Try to read a file
        with open('/etc/passwd', 'r') as f:
            data = f.read()
        return {}
"""
        sandbox = BotSandbox()
        bot_instance = sandbox.execute_bot_code(malicious_code, "MaliciousBot")

        # File access is blocked at runtime when on_tick is called
        mock_state = create_mock_state()

        with pytest.raises(SandboxSecurityError, match="blocked function"):
            sandbox.call_on_tick(bot_instance, mock_state)

    def test_blocks_file_write_attempt(self):
        """Test that bot cannot write files."""
        malicious_code = """
class MaliciousBot:
    def on_tick(self, state):
        # Try to write a file
        with open('/tmp/hack.txt', 'w') as f:
            f.write('pwned')
        return {}
"""
        sandbox = BotSandbox()
        bot_instance = sandbox.execute_bot_code(malicious_code, "MaliciousBot")

        # File access is blocked at runtime when on_tick is called
        mock_state = create_mock_state()

        with pytest.raises(SandboxSecurityError, match="blocked function"):
            sandbox.call_on_tick(bot_instance, mock_state)

    def test_blocks_network_import(self):
        """Test that bot cannot import network modules."""
        malicious_code = """
import socket

class MaliciousBot:
    def on_tick(self, state):
        # Try to create network connection
        s = socket.socket()
        return {}
"""
        sandbox = BotSandbox()

        with pytest.raises(SandboxSecurityError, match="Import of module.*not allowed"):
            sandbox.execute_bot_code(malicious_code, "MaliciousBot")

    def test_blocks_os_module_import(self):
        """Test that bot cannot import os module."""
        malicious_code = """
import os

class MaliciousBot:
    def on_tick(self, state):
        # Try to execute system command
        os.system('ls')
        return {}
"""
        sandbox = BotSandbox()

        with pytest.raises(SandboxSecurityError, match="Import of module.*not allowed"):
            sandbox.execute_bot_code(malicious_code, "MaliciousBot")

    def test_blocks_subprocess_import(self):
        """Test that bot cannot import subprocess."""
        malicious_code = """
import subprocess

class MaliciousBot:
    def on_tick(self, state):
        subprocess.run(['ls'])
        return {}
"""
        sandbox = BotSandbox()

        with pytest.raises(SandboxSecurityError, match="Import of module.*not allowed"):
            sandbox.execute_bot_code(malicious_code, "MaliciousBot")

    def test_blocks_eval_builtin(self):
        """Test that eval() is not accessible."""
        malicious_code = """
class MaliciousBot:
    def on_tick(self, state):
        # Try to use eval
        eval('print("pwned")')
        return {}
"""
        sandbox = BotSandbox()

        with pytest.raises(SandboxSecurityError, match="Security restrictions violated|Eval calls"):
            sandbox.execute_bot_code(malicious_code, "MaliciousBot")

    def test_blocks_exec_builtin(self):
        """Test that exec() is not accessible."""
        malicious_code = """
class MaliciousBot:
    def on_tick(self, state):
        # Try to use exec
        exec('import os')
        return {}
"""
        sandbox = BotSandbox()

        with pytest.raises(SandboxSecurityError, match="Security restrictions violated|blocked function"):
            bot_instance = sandbox.execute_bot_code(malicious_code, "MaliciousBot")
            # exec() is None, so calling it raises TypeError which becomes SandboxSecurityError
            mock_state = create_mock_state()
            sandbox.call_on_tick(bot_instance, mock_state)

    def test_blocks_compile_builtin(self):
        """Test that compile() is not accessible."""
        malicious_code = """
class MaliciousBot:
    def on_tick(self, state):
        # Try to use compile
        code = compile('1 + 1', '<string>', 'eval')
        return {}
"""
        sandbox = BotSandbox()

        with pytest.raises(SandboxSecurityError, match="Security restrictions violated|blocked function"):
            bot_instance = sandbox.execute_bot_code(malicious_code, "MaliciousBot")
            # compile() is None, so calling it raises TypeError which becomes SandboxSecurityError
            mock_state = create_mock_state()
            sandbox.call_on_tick(bot_instance, mock_state)

    def test_blocks_globals_access(self):
        """Test that globals() is restricted."""
        malicious_code = """
class MaliciousBot:
    def on_tick(self, state):
        # Try to access globals
        g = globals()
        return {}
"""
        sandbox = BotSandbox()

        with pytest.raises(SandboxSecurityError, match="Security restrictions violated|blocked function"):
            bot_instance = sandbox.execute_bot_code(malicious_code, "MaliciousBot")
            # globals() is None, so calling it raises TypeError which becomes SandboxSecurityError
            mock_state = create_mock_state()
            sandbox.call_on_tick(bot_instance, mock_state)

    def test_blocks_locals_manipulation(self):
        """Test that locals() is restricted."""
        malicious_code = """
class MaliciousBot:
    def on_tick(self, state):
        # Try to manipulate locals
        l = locals()
        return {}
"""
        sandbox = BotSandbox()

        with pytest.raises(SandboxSecurityError, match="Security restrictions violated|blocked function"):
            bot_instance = sandbox.execute_bot_code(malicious_code, "MaliciousBot")
            # locals() is None, so calling it raises TypeError which becomes SandboxSecurityError
            mock_state = create_mock_state()
            sandbox.call_on_tick(bot_instance, mock_state)

    def test_blocks_import_builtin(self):
        """Test that __import__ is blocked."""
        malicious_code = """
class MaliciousBot:
    def on_tick(self, state):
        # Try to use __import__
        os_module = __import__('os')
        return {}
"""
        sandbox = BotSandbox()

        with pytest.raises(SandboxSecurityError, match="__import__|import"):
            sandbox.execute_bot_code(malicious_code, "MaliciousBot")


class TestSandboxMathAllowed:
    """Test that math module is allowed as specified."""

    def test_allows_math_import(self):
        """Test that math module can be imported."""
        safe_code = """
import math

class SafeBot:
    def on_tick(self, state):
        # Use math module
        angle = math.atan2(1, 1)
        return {'accelerate': True}
"""
        sandbox = BotSandbox()

        # Should not raise
        bot_instance = sandbox.execute_bot_code(safe_code, "SafeBot")
        assert bot_instance is not None

    def test_allows_math_functions(self):
        """Test that bot can use math functions."""
        safe_code = """
import math

class MathBot:
    def on_tick(self, state):
        # Use various math functions
        result = math.sqrt(16)
        angle = math.pi / 2
        sine = math.sin(angle)
        return {'accelerate': result == 4.0}
"""
        sandbox = BotSandbox()

        bot_instance = sandbox.execute_bot_code(safe_code, "MathBot")
        assert bot_instance is not None


class TestSandboxTimeout:
    """Test execution timeout enforcement."""

    def test_enforces_timeout_on_infinite_loop(self):
        """Test that infinite loops are killed by timeout."""
        timeout_code = """
class InfiniteBot:
    def on_tick(self, state):
        # Infinite loop
        while True:
            pass
        return {}
"""
        sandbox = BotSandbox(timeout_ms=10)
        bot_instance = sandbox.execute_bot_code(timeout_code, "InfiniteBot")

        # Executing on_tick should timeout
        from app.bot_runtime.types import BotGameState, BotCarState, BotTrackState, BotRaceState

        mock_state = BotGameState(
            car=BotCarState(
                position=(0, 0), heading=0, speed=0, velocity=(0, 0),
                angular_velocity=0, health=100, nitro_charges=2,
                nitro_active=False, current_surface="asphalt", off_track=False
            ),
            track=BotTrackState(
                checkpoints=[], next_checkpoint=0,
                distance_to_boundary_left=50, distance_to_boundary_right=50,
                upcoming_surface="asphalt", upcoming_turn="straight", turn_sharpness=0
            ),
            rays=[],
            opponents=[],
            race=BotRaceState(
                current_checkpoint=0, total_checkpoints=5, position=1,
                total_cars=1, elapsed_time=0, distance_to_finish=1000
            )
        )

        with pytest.raises(SandboxTimeoutError, match="timeout|exceeded"):
            sandbox.call_on_tick(bot_instance, mock_state)


class TestSandboxValidCode:
    """Test that sandbox allows valid, safe bot code."""

    def test_allows_simple_bot(self):
        """Test that simple bot code executes successfully."""
        valid_code = """
class SimpleBot(GuardedBotBase):
    def __init__(self):
        self.name = "Simple Bot"

    def on_tick(self, state):
        return {'accelerate': True, 'brake': False}
"""
        sandbox = BotSandbox()
        bot_instance = sandbox.execute_bot_code(valid_code, "SimpleBot")

        assert bot_instance is not None
        assert bot_instance.name == "Simple Bot"

    def test_allows_bot_with_logic(self):
        """Test that bot with decision logic works."""
        valid_code = """
import math

class SmartBot(GuardedBotBase):
    def __init__(self):
        self.name = "Smart Bot"
        self.checkpoints_seen = 0

    def on_tick(self, state):
        # Simple logic
        speed = state.car.speed
        should_accelerate = speed < 100

        return {
            'accelerate': should_accelerate,
            'brake': not should_accelerate
        }
"""
        sandbox = BotSandbox()
        bot_instance = sandbox.execute_bot_code(valid_code, "SmartBot")

        assert bot_instance is not None
        assert bot_instance.name == "Smart Bot"

    def test_allows_bot_with_memory(self):
        """Test that bot can use self.memory."""
        valid_code = """
class LearningBot(GuardedBotBase):
    def __init__(self):
        self.name = "Learning Bot"
        if not hasattr(self, 'memory'):
            self.memory = {}
        if 'total_ticks' not in self.memory:
            self.memory['total_ticks'] = 0

    def on_tick(self, state):
        # Use regular assignment instead of augmented (RestrictedPython blocks augmented dict assignment)
        self.memory['total_ticks'] = self.memory['total_ticks'] + 1
        return {'accelerate': True}
"""
        sandbox = BotSandbox()
        bot_instance = sandbox.execute_bot_code(valid_code, "LearningBot")

        assert bot_instance is not None
        assert hasattr(bot_instance, 'memory')
        assert bot_instance.memory['total_ticks'] == 0


class TestSandboxEdgeCases:
    """Test edge cases and potential escape attempts."""

    def test_blocks_dunder_methods_escape(self):
        """Test that __class__ and similar escapes are blocked."""
        escape_code = """
class EscapeBot:
    def on_tick(self, state):
        # Try to escape via __class__
        import_func = ().__class__.__bases__[0].__subclasses__()[104].__init__.__globals__['__builtins__']['__import__']
        os = import_func('os')
        return {}
"""
        sandbox = BotSandbox()

        # Should be blocked during execution or raise security error
        with pytest.raises((SandboxSecurityError, AttributeError, TypeError, KeyError)):
            bot_instance = sandbox.execute_bot_code(escape_code, "EscapeBot")

    def test_blocks_bytecode_manipulation(self):
        """Test that bytecode cannot be manipulated."""
        escape_code = """
class BytecodeBot:
    def on_tick(self, state):
        # Try to access function code objects
        code = self.on_tick.__code__
        return {}
"""
        sandbox = BotSandbox()

        # Should either block or restrict access
        with pytest.raises((SandboxSecurityError, AttributeError)):
            bot_instance = sandbox.execute_bot_code(escape_code, "BytecodeBot")
            # Even if bot loads, calling method should fail
            from app.bot_runtime.types import BotGameState, BotCarState, BotTrackState, BotRaceState
            mock_state = BotGameState(
                car=BotCarState(
                    position=(0, 0), heading=0, speed=0, velocity=(0, 0),
                    angular_velocity=0, health=100, nitro_charges=2,
                    nitro_active=False, current_surface="asphalt", off_track=False
                ),
                track=BotTrackState(
                    checkpoints=[], next_checkpoint=0,
                    distance_to_boundary_left=50, distance_to_boundary_right=50,
                    upcoming_surface="asphalt", upcoming_turn="straight", turn_sharpness=0
                ),
                rays=[],
                opponents=[],
                race=BotRaceState(
                    current_checkpoint=0, total_checkpoints=5, position=1,
                    total_cars=1, elapsed_time=0, distance_to_finish=1000
                )
            )
            sandbox.call_on_tick(bot_instance, mock_state)
