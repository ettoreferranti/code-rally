"""Async LLM strategist (issue #152).

Owns one async task per car. Pulls the latest observation, asks the
injected generate_fn for an Intent (JSON), parses it, and exposes the
latest valid Intent via a synchronous accessor for the 20Hz controller.

Failures are non-fatal: timeouts, parse errors, validation errors, and
any other exceptions are swallowed and the previous valid Intent is
preserved. If no Intent has ever been produced, latest_intent() returns
None and the controller must fall back to its own safe defaults.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Awaitable, Callable, Optional

from pydantic import ValidationError

from app.agents.intent import Intent

logger = logging.getLogger(__name__)


GenerateFn = Callable[[str], Awaitable[str]]


_SYSTEM_PROMPT = (
    "You are driving a rally car. Given the current observation, decide your "
    "high-level driving intent for the next second.\n"
    "Output ONLY a JSON object with exactly these fields:\n"
    '  "target_speed_kmh": number, 0..300\n'
    '  "racing_line_offset_m": number, -10..10  (negative = left of centre)\n'
    '  "aggression": number, 0..1  (0 = cautious, 1 = aggressive)\n'
    "Output nothing else. No prose, no markdown, no code fences."
)


def build_prompt(observation: str) -> str:
    """Assemble the full prompt sent to the generation backend."""
    return (
        f"{_SYSTEM_PROMPT}\n\n"
        f"Observation:\n{observation}\n\n"
        f"Intent JSON:"
    )


class LLMStrategist:
    """Run an LLM at ~1Hz to translate observations into Intents.

    Args:
        generate_fn: async callable taking a prompt and returning text.
            In production this is backed by MLX (see mlx_runtime); in
            tests it is a mock that lets us drive every code path
            without loading a real model.
        tick_interval_s: how often the background loop calls generate_fn.
        timeout_s: per-call timeout. Timeouts are dropped, not raised.
    """

    def __init__(
        self,
        generate_fn: GenerateFn,
        tick_interval_s: float = 1.0,
        timeout_s: float = 2.0,
    ) -> None:
        self._generate_fn = generate_fn
        self._tick_interval_s = tick_interval_s
        self._timeout_s = timeout_s
        self._latest_observation: Optional[str] = None
        self._latest_intent: Optional[Intent] = None
        self._task: Optional[asyncio.Task] = None

    def set_observation(self, observation: str) -> None:
        """Update the observation seen by the next tick."""
        self._latest_observation = observation

    def latest_intent(self) -> Optional[Intent]:
        """Return the most recently parsed Intent, or None if none yet."""
        return self._latest_intent

    async def tick_once(self) -> Optional[Intent]:
        """Run a single generate+parse cycle.

        Exposed for deterministic testing. Returns the Intent produced
        this tick (which is also stored in latest_intent), or None if
        the call timed out, failed, or produced unparseable output.
        Never raises.
        """
        observation = self._latest_observation
        if observation is None:
            return None

        try:
            raw = await asyncio.wait_for(
                self._generate_fn(build_prompt(observation)),
                timeout=self._timeout_s,
            )
        except asyncio.TimeoutError:
            logger.debug("LLM strategist tick timed out after %.1fs", self._timeout_s)
            return None
        except Exception:
            logger.exception("LLM strategist generate_fn raised")
            return None

        intent = _parse_intent(raw)
        if intent is not None:
            self._latest_intent = intent
        return intent

    async def start(self) -> None:
        """Spawn the background tick loop. No-op if already running."""
        if self._task is not None and not self._task.done():
            return
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        """Cancel the background tick loop and wait for it to exit."""
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None

    async def _run(self) -> None:
        try:
            while True:
                await self.tick_once()
                await asyncio.sleep(self._tick_interval_s)
        except asyncio.CancelledError:
            raise


def _parse_intent(raw: str) -> Optional[Intent]:
    """Extract an Intent from raw model output. Tolerates surrounding noise."""
    if not raw:
        return None

    # Find the first {...} block. Models often emit a code fence or a stray
    # leading token despite the system prompt. We do not attempt brace
    # balancing for nested JSON because the Intent schema is flat.
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    candidate = raw[start : end + 1]

    try:
        data = json.loads(candidate)
    except json.JSONDecodeError:
        return None

    try:
        return Intent.model_validate(data)
    except ValidationError:
        return None
