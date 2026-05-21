"""Structured driving intent emitted by the LLM strategist (issue #152).

Field history
-------------
- Original three fields (#152): ``target_speed_kmh``, ``racing_line_offset_m``,
  ``aggression`` — sufficient for a single car driving alone.
- Driving-uplift fields (this change): ``use_nitro``, ``target_opponent_index``,
  ``tactic`` — let the LLM express nitro usage and tactical interaction
  with another car. Defaults preserve backward compatibility: a model
  that emits only the original three fields still parses, and the
  controller treats it as the historic behaviour (no nitro, no targeting).
"""

from typing import Literal, Optional

from pydantic import BaseModel, Field


# Allowed values must match the ``tactic`` handling in
# ``app.agents.controller``. Adding a value requires extending the
# controller's tactic-resolution logic.
Tactic = Literal["race", "overtake", "block", "pit"]


class Intent(BaseModel):
    """High-level driving intent produced by the strategist at ~1Hz.

    The deterministic controller consumes the latest Intent every tick
    (20Hz) and translates it into concrete steer/throttle/brake/nitro
    inputs.

    Bounds are intentionally generous: the controller is responsible for
    clamping to physically achievable values for the current car/surface.

    Field semantics:

    - ``use_nitro``: when ``True`` AND nitro charges are available, the
      controller passes the flag through to ``PlayerInput.nitro``. Has
      no effect when no charges remain. The LLM should set this only
      when it expects clear straight-line gains (long straight, last
      sector, overtake setup).
    - ``target_opponent_index``: index into the observation's opponent
      slots (0 = ``opponent[1]``, 1 = ``opponent[2]``). ``None`` means
      no target. The controller uses this together with ``tactic`` to
      shift the racing line toward/away from the targeted opponent.
    - ``tactic``: drives how the controller interprets a target opponent.
      "race" ignores the opponent and follows the regular racing line.
      "overtake" biases the lookahead away from the opponent (try to
      pass on the open side). "pit" biases toward the opponent (deliberate
      contact). "block" biases toward the inside of the upcoming corner
      to deny a chasing opponent the racing line.
    """

    target_speed_kmh: float = Field(ge=0, le=400)
    racing_line_offset_m: float = Field(ge=-20, le=20)
    aggression: float = Field(ge=0, le=1)
    use_nitro: bool = False
    target_opponent_index: Optional[int] = Field(default=None, ge=0, le=1)
    tactic: Tactic = "race"
