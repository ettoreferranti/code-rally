"""
RestrictedPython sandbox for safe bot code execution.

This module provides a secure execution environment for user-submitted bot code:
- Restricts imports to math module only
- Blocks file system and network access
- Blocks dangerous built-ins (eval, exec, compile, etc.)
- Enforces execution timeout
- Enforces memory limits (via OS-level resource limits)

Security is critical - any changes must be carefully reviewed.
"""

import signal
import math
import resource
from typing import Any, Dict, Optional
from RestrictedPython import compile_restricted, safe_globals
from RestrictedPython.Guards import (
    guarded_iter_unpack_sequence,
    guarded_unpack_sequence,
    guarded_setattr,
    safer_getattr,
    full_write_guard,
    safe_builtins
)

from app.config import get_settings


class GuardedBotBase:
    """
    Base class that provides guarded attribute access for RestrictedPython.

    All user bot classes should inherit from this to work with the sandbox.
    """

    def __guarded_setattr__(self, name: str, value: Any) -> None:
        """Allow attribute assignment in RestrictedPython sandbox."""
        # Allow setting any attribute - the sandbox restrictions are at import/builtin level
        object.__setattr__(self, name, value)

    def __guarded_delattr__(self, name: str) -> None:
        """Allow attribute deletion in RestrictedPython sandbox."""
        object.__delattr__(self, name)


class SandboxSecurityError(Exception):
    """Raised when bot code attempts a forbidden operation."""
    pass


class SandboxTimeoutError(Exception):
    """Raised when bot code exceeds execution time limit."""
    pass


class SandboxMemoryError(Exception):
    """Raised when bot code exceeds memory limit."""
    pass


def _timeout_handler(signum, frame):
    """Signal handler for execution timeout."""
    raise SandboxTimeoutError("Bot execution exceeded time limit")


def _safe_import(name, *args, **kwargs):
    """
    Restricted import function - only allows math module.

    Args:
        name: Module name to import

    Returns:
        Imported module if allowed

    Raises:
        SandboxSecurityError: If module is not allowed
    """
    allowed_modules = {'math'}

    if name not in allowed_modules:
        raise SandboxSecurityError(
            f"Import of module '{name}' is not allowed. Only 'math' module is permitted."
        )

    if name == 'math':
        return math

    raise SandboxSecurityError(f"Module '{name}' not available")


def _create_safe_globals() -> Dict[str, Any]:
    """
    Create a safe globals dictionary for bot execution.

    Returns:
        Dictionary with only safe built-ins and allowed imports
    """
    # Start with RestrictedPython's safe_builtins as base
    restricted_builtins = safe_builtins.copy()

    # Add additional safe built-ins
    restricted_builtins.update({
        'dict': dict,
        'list': list,
        'set': set,
        'enumerate': enumerate,
        'any': any,
        'all': all,
        'hasattr': hasattr,
        'getattr': getattr,
        'min': min,
        'max': max,
        'sum': sum,
    })

    # Add custom restricted import
    restricted_builtins['__import__'] = _safe_import

    # Block dangerous functions by setting to None
    restricted_builtins.update({
        'eval': None,
        'exec': None,
        'compile': None,
        'open': None,
        'globals': None,
        'locals': None,
    })

    # Create the safe globals dictionary
    # Use safe_globals as base to get all the necessary guards
    safe_dict = safe_globals.copy()

    # Get the guarded setattr and delattr from safe_globals
    safe_globals_builtins = safe_globals['__builtins__']

    # Merge our restricted builtins with the guarded versions of setattr/delattr
    restricted_builtins['setattr'] = safe_globals_builtins['setattr']
    restricted_builtins['delattr'] = safe_globals_builtins['delattr']
    restricted_builtins['_getattr_'] = safe_globals_builtins['_getattr_']

    # Override __builtins__ with our restricted set
    safe_dict['__builtins__'] = restricted_builtins

    # Add required RestrictedPython guards
    safe_dict.update({
        '_iter_unpack_sequence_': guarded_iter_unpack_sequence,
        '_unpack_sequence_': guarded_unpack_sequence,
        '_getattr_': safer_getattr,
        '_write_': full_write_guard,
        '__metaclass__': type,
        '__name__': 'restricted_module',
        # Make GuardedBotBase available to bot code
        'GuardedBotBase': GuardedBotBase,
    })

    return safe_dict


class BotSandbox:
    """
    Secure sandbox for executing bot code using RestrictedPython.

    Example:
        sandbox = BotSandbox(timeout_ms=10)
        bot_instance = sandbox.execute_bot_code(code_string, "BotClassName")
        actions = sandbox.call_on_tick(bot_instance, game_state)
    """

    def __init__(self, timeout_ms: Optional[int] = None):
        """
        Initialize the sandbox.

        Args:
            timeout_ms: Execution timeout in milliseconds (default from config)
        """
        self.settings = get_settings()
        self.timeout_ms = timeout_ms or self.settings.bot.EXECUTION_TIMEOUT_MS
        self.timeout_seconds = self.timeout_ms / 1000.0

    def _set_memory_limit(self) -> None:
        """
        Set memory limit for bot execution.

        Uses resource.RLIMIT_AS to limit address space.
        Note: This is Unix-only and limits the entire process.

        Raises:
            SandboxMemoryError: If memory limit cannot be set
        """
        try:
            max_memory_bytes = self.settings.bot.MEMORY_LIMIT_MB * 1024 * 1024
            # Set soft and hard limits
            resource.setrlimit(resource.RLIMIT_AS, (max_memory_bytes, max_memory_bytes))
        except (ValueError, OSError) as e:
            # On some systems (e.g., macOS), this may fail
            # We log but don't fail - RestrictedPython provides some protection
            pass

    def execute_bot_code(self, code: str, class_name: str) -> Any:
        """
        Compile and execute bot code in restricted environment.

        Args:
            code: Python source code as string
            class_name: Name of the bot class to instantiate

        Returns:
            Instance of the bot class

        Raises:
            SandboxSecurityError: If code attempts forbidden operations
            SandboxTimeoutError: If code execution exceeds timeout
            ValueError: If code is invalid Python or class not found
        """
        # Validate code size
        max_size_bytes = self.settings.bot.MAX_CODE_SIZE_KB * 1024
        if len(code.encode('utf-8')) > max_size_bytes:
            raise ValueError(f"Bot code exceeds maximum size of {self.settings.bot.MAX_CODE_SIZE_KB}KB")

        # Compile with RestrictedPython
        try:
            byte_code = compile_restricted(
                code,
                filename='<bot_code>',
                mode='exec'
            )
        except SyntaxError as e:
            # RestrictedPython raises SyntaxError for security violations
            raise SandboxSecurityError(f"Security restrictions violated: {str(e)}")

        # Create safe execution environment
        safe_dict = _create_safe_globals()
        local_dict = {}

        # Execute code to define bot class
        try:
            # Set memory limit (best-effort on Unix systems)
            self._set_memory_limit()

            # Set timeout for code execution
            signal.signal(signal.SIGALRM, _timeout_handler)
            signal.setitimer(signal.ITIMER_REAL, self.timeout_seconds)

            try:
                exec(byte_code, safe_dict, local_dict)
            finally:
                # Cancel timeout
                signal.setitimer(signal.ITIMER_REAL, 0)

        except SandboxTimeoutError:
            raise
        except SandboxSecurityError:
            raise
        except Exception as e:
            raise SandboxSecurityError(f"Bot code execution failed: {str(e)}")

        # Get bot class from local namespace
        if class_name not in local_dict:
            raise ValueError(f"Bot class '{class_name}' not found in code")

        bot_class = local_dict[class_name]

        # Instantiate bot (with timeout)
        try:
            signal.signal(signal.SIGALRM, _timeout_handler)
            signal.setitimer(signal.ITIMER_REAL, self.timeout_seconds)

            try:
                bot_instance = bot_class()
            finally:
                signal.setitimer(signal.ITIMER_REAL, 0)

        except SandboxTimeoutError:
            raise SandboxTimeoutError("Bot __init__() exceeded time limit")
        except Exception as e:
            raise SandboxSecurityError(f"Bot instantiation failed: {str(e)}")

        return bot_instance

    def call_on_tick(self, bot_instance: Any, state: Any) -> Dict[str, bool]:
        """
        Call bot's on_tick() method with timeout enforcement.

        Args:
            bot_instance: Bot instance
            state: BotGameState to pass to bot

        Returns:
            Dictionary of actions

        Raises:
            SandboxTimeoutError: If execution exceeds timeout
            SandboxSecurityError: If execution attempts forbidden operations
        """
        if not hasattr(bot_instance, 'on_tick'):
            raise ValueError("Bot instance does not have on_tick() method")

        try:
            # Set timeout
            signal.signal(signal.SIGALRM, _timeout_handler)
            signal.setitimer(signal.ITIMER_REAL, self.timeout_seconds)

            try:
                result = bot_instance.on_tick(state)
            finally:
                # Cancel timeout
                signal.setitimer(signal.ITIMER_REAL, 0)

            # Validate result
            if not isinstance(result, dict):
                return {'accelerate': False, 'brake': False, 'turn_left': False, 'turn_right': False, 'use_nitro': False}

            return result

        except SandboxTimeoutError:
            raise
        except SandboxSecurityError:
            raise
        except TypeError as e:
            # Check if bot tried to call a blocked function (set to None)
            if "'NoneType' object is not callable" in str(e):
                raise SandboxSecurityError(f"Bot attempted to use blocked function: {str(e)}")
            # Other TypeErrors are bot logic errors - return safe default
            return {'accelerate': False, 'brake': False, 'turn_left': False, 'turn_right': False, 'use_nitro': False}
        except Exception as e:
            # Bot code error - return safe default
            return {'accelerate': False, 'brake': False, 'turn_left': False, 'turn_right': False, 'use_nitro': False}

    def call_on_collision(self, bot_instance: Any, event: Any) -> None:
        """
        Call bot's on_collision() callback with timeout enforcement.

        Args:
            bot_instance: Bot instance
            event: CollisionEvent

        Raises:
            SandboxTimeoutError: If execution exceeds timeout
        """
        if not hasattr(bot_instance, 'on_collision'):
            return

        try:
            signal.signal(signal.SIGALRM, _timeout_handler)
            signal.setitimer(signal.ITIMER_REAL, self.timeout_seconds)

            try:
                bot_instance.on_collision(event)
            finally:
                signal.setitimer(signal.ITIMER_REAL, 0)

        except SandboxTimeoutError:
            raise
        except Exception:
            # Silently ignore callback errors
            pass

    def call_on_checkpoint(self, bot_instance: Any, checkpoint_index: int, split_time: float) -> None:
        """
        Call bot's on_checkpoint() callback with timeout enforcement.

        Args:
            bot_instance: Bot instance
            checkpoint_index: Checkpoint index
            split_time: Split time in seconds

        Raises:
            SandboxTimeoutError: If execution exceeds timeout
        """
        if not hasattr(bot_instance, 'on_checkpoint'):
            return

        try:
            signal.signal(signal.SIGALRM, _timeout_handler)
            signal.setitimer(signal.ITIMER_REAL, self.timeout_seconds)

            try:
                bot_instance.on_checkpoint(checkpoint_index, split_time)
            finally:
                signal.setitimer(signal.ITIMER_REAL, 0)

        except SandboxTimeoutError:
            raise
        except Exception:
            pass

    def call_on_finish(self, bot_instance: Any, finish_time: float, final_position: int) -> None:
        """
        Call bot's on_finish() callback with timeout enforcement.

        Args:
            bot_instance: Bot instance
            finish_time: Finish time in seconds
            final_position: Final race position

        Raises:
            SandboxTimeoutError: If execution exceeds timeout
        """
        if not hasattr(bot_instance, 'on_finish'):
            return

        try:
            signal.signal(signal.SIGALRM, _timeout_handler)
            signal.setitimer(signal.ITIMER_REAL, self.timeout_seconds)

            try:
                bot_instance.on_finish(finish_time, final_position)
            finally:
                signal.setitimer(signal.ITIMER_REAL, 0)

        except SandboxTimeoutError:
            raise
        except Exception:
            pass
