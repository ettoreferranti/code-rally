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
import time
from typing import Awaitable, Callable, Optional, Tuple

from pydantic import ValidationError

from app.agents.intent import Intent

logger = logging.getLogger(__name__)


GenerateFn = Callable[[str], Awaitable[str]]


# Domain floor on target speed. Intents below this are rejected by
# `_parse_intent` so the strategist keeps the previous good intent and
# the car keeps racing (#162). A small 1.5B model otherwise converges
# to `target_speed_kmh=0` on tricky surfaces, parking the car.
_MIN_TARGET_SPEED_KMH = 30.0


DEFAULT_SYSTEM_PROMPT = (
    "You are a rally driver racing to finish the stage AS FAST AS POSSIBLE. "
    "Top speed is around 180 km/h. Wet, gravel, and ice surfaces reduce "
    "grip but you still race — pick a safer speed and a wider racing line, "
    "but never stop.\n\n"
    "Given the observation, decide your driving intent for the next second.\n\n"
    "Output ONLY a JSON object with these fields:\n"
    '  "target_speed_kmh": number between 40 and 200\n'
    "     (40-70 on tight corners or low-grip surfaces; 80-130 on flowing "
    "corners; 130-180 on straights. NEVER output less than 40.)\n"
    '  "racing_line_offset_m": number between -10 and 10 (negative = left of centre)\n'
    '  "aggression": number between 0.3 and 1.0 '
    "(0.3 = careful, 1.0 = full attack; use 0.5+ on most segments)\n\n"
    "Examples:\n"
    "Observation: speed=20 km/h, next checkpoint=120m straight ahead, surface=asphalt\n"
    'Intent: {"target_speed_kmh": 170, "racing_line_offset_m": 0, "aggression": 0.7}\n\n'
    "Observation: speed=120 km/h, next checkpoint=40m bearing 45 deg, surface=gravel\n"
    'Intent: {"target_speed_kmh": 65, "racing_line_offset_m": -2, "aggression": 0.5}\n\n'
    "Output nothing else. No prose, no markdown, no code fences."
)


def build_prompt(observation: str, system_prompt: Optional[str] = None) -> str:
    """Assemble the full prompt sent to the generation backend.

    Args:
        observation: The formatted observation string for this tick.
        system_prompt: Optional per-bot system-prompt override (Tinker
            UI lets users edit this). Defaults to ``DEFAULT_SYSTEM_PROMPT``.
    """
    base = system_prompt if system_prompt is not None else DEFAULT_SYSTEM_PROMPT
    return (
        f"{base}\n\n"
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
        system_prompt: optional per-bot system prompt. None → use
            ``DEFAULT_SYSTEM_PROMPT``. Set by the Tinker UI when the LLM
            bot stored its own prompt.
    """

    def __init__(
        self,
        generate_fn: GenerateFn,
        tick_interval_s: float = 1.0,
        timeout_s: float = 2.0,
        system_prompt: Optional[str] = None,
    ) -> None:
        self._generate_fn = generate_fn
        self._tick_interval_s = tick_interval_s
        self._timeout_s = timeout_s
        self._system_prompt = system_prompt
        self._latest_observation: Optional[str] = None
        self._latest_intent: Optional[Intent] = None
        # Server-side Unix timestamp of when `_latest_intent` was produced.
        # Read by consumers (e.g. WebSocket payload) to detect stale intents.
        self._latest_intent_ts: Optional[float] = None
        self._task: Optional[asyncio.Task] = None

    def set_observation(self, observation: str) -> None:
        """Update the observation seen by the next tick."""
        self._latest_observation = observation

    def latest_intent(self) -> Optional[Intent]:
        """Return the most recently parsed Intent, or None if none yet."""
        return self._latest_intent

    def latest_intent_with_ts(self) -> Tuple[Optional[Intent], Optional[float]]:
        """Return (intent, server-timestamp) — both None if no intent yet.

        The timestamp is captured when the intent was stored, so consumers
        can compute staleness (e.g. fade a UI element when intent age > 2s).
        """
        return self._latest_intent, self._latest_intent_ts

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
                self._generate_fn(build_prompt(observation, self._system_prompt)),
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
            self._latest_intent_ts = time.time()
            logger.info(
                "strategist intent: target=%.0f km/h, offset=%+.1f m, aggression=%.2f",
                intent.target_speed_kmh,
                intent.racing_line_offset_m,
                intent.aggression,
            )
        else:
            # Surface parse failures too — useful when the model emits malformed
            # JSON consistently (one of the candidate causes for #162).
            logger.info(
                "strategist intent: PARSE FAILURE (raw=%r)",
                raw[:200] if raw else raw,
            )
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

    # Find the FIRST complete {...} block. Models sometimes emit a code
    # fence, a stray leading token, or — as observed with Qwen2.5-1.5B in
    # #162 — keep repeating the same object until the token budget runs
    # out. Taking up to the LAST `}` (the original behaviour) bundles all
    # the repeats together as one invalid blob; taking the first `}` after
    # the first `{` gives us the first complete object every time.
    #
    # The Intent schema is flat (no nested objects, no `}` inside string
    # values), so a literal first-`}` scan is safe. If the schema ever
    # gains nested objects, switch to a brace-balanced scan instead.
    start = raw.find("{")
    if start == -1:
        return None
    end = raw.find("}", start)
    if end == -1:
        return None
    candidate = raw[start : end + 1]

    try:
        data = json.loads(candidate)
    except json.JSONDecodeError:
        return None

    try:
        intent = Intent.model_validate(data)
    except ValidationError:
        return None

    # Reject "stop" / "crawl" intents so the strategist keeps the last good
    # one. Small instruction-tuned models drift toward target=0 on tricky
    # surfaces despite the prompt — see #162.
    if intent.target_speed_kmh < _MIN_TARGET_SPEED_KMH:
        return None

    return intent
