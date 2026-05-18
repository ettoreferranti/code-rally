"""LLM-driven car: the third driver kind (issue #155).

Bundles the three primitives merged in #152/#153/#154 into one
per-car object the engine can talk to alongside humans and Python
sandbox bots:

  - LLMStrategist      ~1Hz async task, observation → Intent
  - format_observation pure function, BotGameState → text
  - Controller         20Hz deterministic, Intent → ControlInputs

Lifecycle is bound to the race lifecycle by the engine:
  - ``await bot.start()`` after start_race spawns the strategist task
  - ``await bot.stop()`` on stop_loop cancels it

The per-tick path is fully synchronous. ``get_inputs`` only swaps an
in-memory observation string and reads the latest cached Intent — it
never awaits the LLM, so the engine tick can never be blocked by model
latency. The strategist may be silent (still loading, slow, or failing
every call); the Controller is responsible for the graceful fallback.

Note on return type: the engine's ``PlayerInput`` is a tuple of bool
flags. The Controller already emits bool flags via ``ControlInputs``,
so we return that and let the engine map it. The shorthand
``{steer, throttle, brake}`` in the issue description refers to the
same set of inputs in a different surface form.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple

from app.agents.controller import Controller, ControlInputs
from app.agents.intent import Intent
from app.agents.llm_strategist import GenerateFn, LLMStrategist
from app.agents.observation import format_observation
from app.bot_runtime.types import BotGameState

logger = logging.getLogger(__name__)


class LLMBot:
    """Per-car LLM driver. Owns one strategist task and one controller."""

    def __init__(
        self,
        generate_fn: GenerateFn,
        controller: Optional[Controller] = None,
        strategist_kwargs: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._strategist = LLMStrategist(
            generate_fn=generate_fn,
            **(strategist_kwargs or {}),
        )
        self._controller = controller or Controller()

    async def start(self) -> None:
        """Spawn the background strategist task. Idempotent."""
        await self._strategist.start()

    async def stop(self) -> None:
        """Cancel the background strategist task and wait for it to exit."""
        await self._strategist.stop()

    def get_inputs(self, state: BotGameState) -> ControlInputs:
        """Compute the next-tick control flags. Never raises, never awaits."""
        self._strategist.set_observation(format_observation(state))
        return self._controller.compute(self._strategist.latest_intent(), state)

    def latest_intent_with_ts(self) -> Tuple[Optional[Intent], Optional[float]]:
        """Pass-through for the strategist's (intent, ts) snapshot.

        Consumed by the engine when assembling the WS game_state payload —
        if the strategist has produced an intent, the snapshot exposes it
        for the frontend thought-bubble UI.
        """
        return self._strategist.latest_intent_with_ts()
