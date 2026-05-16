"""Structured driving intent emitted by the LLM strategist (issue #152)."""

from pydantic import BaseModel, Field


class Intent(BaseModel):
    """High-level driving intent produced by the strategist at ~1Hz.

    The deterministic controller consumes the latest Intent every tick
    (20Hz) and translates it into concrete steer/throttle/brake inputs.

    Bounds are intentionally generous: the controller is responsible for
    clamping to physically achievable values for the current car/surface.
    """

    target_speed_kmh: float = Field(ge=0, le=400)
    racing_line_offset_m: float = Field(ge=-20, le=20)
    aggression: float = Field(ge=0, le=1)
