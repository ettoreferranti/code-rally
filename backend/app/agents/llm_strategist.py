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


# User-editable: persona + driving heuristics. Surfaces in the Tinker UI
# as the "Driving strategy" textarea. Customise freely — the I/O contract
# below is always appended on top, so the model still sees the JSON
# format requirements even if the strategy text doesn't mention them.
DEFAULT_STRATEGY_PROMPT = (
    "You are an expert rally driver. Your job is to finish the stage as "
    "quickly as possible without crashing. Top speed is ~180 km/h.\n\n"
    "Driving principles:\n"
    "- Cornering: brake BEFORE the corner (look at next_turn and "
    "  sharpness), apex tight (negative offset into a left turn, "
    "  positive into a right), accelerate on the exit. Sharper corners "
    "  (sharpness > 0.5) need bigger speed drops.\n"
    "- Racing line: stay wide on entry, clip the apex, drift wide on "
    "  exit. The offset is in metres from the track centreline.\n"
    "- Surfaces: asphalt is full grip; wet ~85%, gravel ~70%, ice ~50%. "
    "  Drop target speed and widen the line on low-grip surfaces. Watch "
    "  upcoming_surface so you brake before a surface change.\n"
    "- Track edges: edge_left / edge_right tell you how much room you "
    "  have. If one is near zero, pull toward the other side.\n"
    "- Nitro: use it on long straights or to complete an overtake. "
    "  Don't waste charges mid-corner.\n"
    "- Other cars: in close racing, set target_opponent_index and a "
    "  tactic. 'overtake' to pass cleanly, 'pit' to bump them off line, "
    "  'block' to defend the inside of the next corner. Otherwise leave "
    "  tactic='race' and ignore other cars.\n\n"
    "Never set a target below 40 km/h — keep moving even on tricky "
    "surfaces."
)

# Invariant. Must stay in sync with ``_parse_intent`` and the ``Intent``
# pydantic model — anything that loosens these constraints risks the
# controller silently falling back to defaults on parse failures.
# NOT exposed to users.
PROTOCOL_PROMPT = (
    "Output ONLY a JSON object. No prose, no markdown, no code fences.\n\n"
    "Required fields:\n"
    '  "target_speed_kmh": number 40–200 '
    "(40–70 tight corners or low grip; 80–130 flowing corners; 130–180 "
    "straights). NEVER below 40.\n"
    '  "racing_line_offset_m": number -10 to 10 '
    "(negative = left of centre, positive = right of centre).\n"
    '  "aggression": number 0.3–1.0 '
    "(0.3 = careful, 1.0 = full attack).\n\n"
    "Optional fields (omit when not relevant; defaults shown):\n"
    '  "use_nitro": true|false (default false). Set true ONLY on long '
    "straights or to finish an overtake; ignored when nitro charges = 0.\n"
    '  "target_opponent_index": 0|1|null (default null). 0 = opponent[1], '
    "1 = opponent[2] from the observation. null = no target.\n"
    '  "tactic": "race"|"overtake"|"block"|"pit" (default "race"). '
    "Only matters when a target_opponent_index is set (except 'block', "
    "which uses the upcoming turn).\n\n"
    "Examples:\n"
    "Observation: long straight, no nearby opponents, asphalt\n"
    'Intent: {"target_speed_kmh": 175, "racing_line_offset_m": 0, '
    '"aggression": 0.9, "use_nitro": true}\n\n'
    "Observation: 40m to sharp left corner, sharpness=0.7, gravel\n"
    'Intent: {"target_speed_kmh": 65, "racing_line_offset_m": 4, '
    '"aggression": 0.6}\n  '
    "(positive offset = stay wide on the entry of the left-hander)\n\n"
    "Observation: opponent[1] dist=30m bearing=15 deg closing, "
    "straight ahead\n"
    'Intent: {"target_speed_kmh": 160, "racing_line_offset_m": -5, '
    '"aggression": 0.9, "target_opponent_index": 0, "tactic": "overtake"}\n\n'
    "Observation: opponent[1] dist=18m bearing=180 deg closing, "
    "next_turn=right sharpness=0.5\n"
    'Intent: {"target_speed_kmh": 110, "racing_line_offset_m": 0, '
    '"aggression": 0.8, "tactic": "block"}\n  '
    "(no target needed; block uses the upcoming turn)\n\n"
    "Output the JSON only."
)


def build_prompt(observation: str, system_prompt: Optional[str] = None) -> str:
    """Assemble the full prompt sent to the generation backend.

    Layout: <strategy>\\n\\n<PROTOCOL>\\n\\nObservation:\\n...
    The protocol section is always appended so user-supplied strategies
    can't accidentally break the JSON contract.

    Args:
        observation: The formatted observation string for this tick.
        system_prompt: Optional per-bot strategy text (Tinker UI lets
            users edit this). Defaults to ``DEFAULT_STRATEGY_PROMPT``.
    """
    strategy = system_prompt if system_prompt is not None else DEFAULT_STRATEGY_PROMPT
    return (
        f"{strategy}\n\n"
        f"{PROTOCOL_PROMPT}\n\n"
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
            Default 15.0s — generous enough to cover the common 1.5B–7B
            MLX models (7B-Q4 first calls can take 3–5 s on M4 Pro). The
            engine's ``add_llm_player`` plumbs a model-size-aware override
            in via ``estimate_timeout_for_model``. A previous 2.0 s default
            silently broke 7B+ models because every tick timed out before
            the generate could finish.
        system_prompt: optional per-bot driving-strategy text. None →
            use ``DEFAULT_STRATEGY_PROMPT``. Set by the Tinker UI when
            the LLM bot stored its own strategy. The I/O protocol is
            always appended on top of this; see ``build_prompt``.
    """

    def __init__(
        self,
        generate_fn: GenerateFn,
        tick_interval_s: float = 1.0,
        timeout_s: float = 15.0,
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
            target_suffix = (
                f", target_opp=#{intent.target_opponent_index}"
                if intent.target_opponent_index is not None
                else ""
            )
            logger.info(
                "strategist intent: target=%.0f km/h, offset=%+.1f m, "
                "aggression=%.2f, nitro=%s, tactic=%s%s",
                intent.target_speed_kmh,
                intent.racing_line_offset_m,
                intent.aggression,
                "Y" if intent.use_nitro else "N",
                intent.tactic,
                target_suffix,
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

    # Clamp out-of-range numeric values BEFORE validation. Observed: small
    # MLX models (Qwen 1.5B/3B Q4) routinely emit values well outside the
    # documented ranges — e.g. ``racing_line_offset_m: -130`` when the
    # protocol says "-10 to 10". Rejecting these as ValidationError drops
    # the entire intent and forces the controller into fallback cruise
    # for that tick. Clamping preserves the LLM's directional preference
    # (still max-left) inside the schema budget so the strategist keeps
    # producing usable intents.
    _clamp_numeric_fields(data)

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


# Fields with documented numeric ranges that the LLM frequently overshoots.
# Kept in lock-step with the ``Intent`` pydantic model's Field bounds — if
# the schema bounds change, update these too.
_INTENT_NUMERIC_BOUNDS = {
    "target_speed_kmh": (0.0, 400.0),
    "racing_line_offset_m": (-20.0, 20.0),
    "aggression": (0.0, 1.0),
}


def _clamp_numeric_fields(data: dict) -> None:
    """In-place clamp out-of-range numeric Intent fields to schema bounds.

    Only adjusts numeric values that are present and outside the bounds —
    leaves booleans, strings, missing keys, and in-range values untouched
    (so they go through normal pydantic validation as before).
    Logs INFO when a clamp fires so the LLM's misbehaviour stays visible.
    """
    for key, (lo, hi) in _INTENT_NUMERIC_BOUNDS.items():
        if key not in data:
            continue
        val = data[key]
        # bool is a subclass of int in Python — exclude it explicitly so
        # ``True``/``False`` aren't accidentally treated as 1/0 numerics.
        if isinstance(val, bool) or not isinstance(val, (int, float)):
            continue
        if val < lo or val > hi:
            clamped = lo if val < lo else hi
            logger.info(
                "intent field %s out of range (got %s, clamped to %s)",
                key, val, clamped,
            )
            data[key] = clamped
