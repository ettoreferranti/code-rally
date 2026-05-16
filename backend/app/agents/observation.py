"""Compact text observation for the LLM strategist (issue #153).

Translates the existing per-car ``BotGameState`` (already produced by
the bot_runtime for sandboxed Python bots) into a fixed-shape text
prompt fragment suitable for a small LLM.

Design notes (worth knowing before changing this file):

- **Compact and stable in length.** The strategist's prompt size must
  be predictable, so we always emit exactly 3 checkpoint slots and
  exactly 2 opponent slots (filling with "none" when fewer are
  available). Adding fields is fine; making fields variable in count
  is not — it changes the model's effective context budget mid-race.

- **Vector state only.** No images, no raycast lists. A 1.5B model
  cannot reason about 7 raycast floats usefully at 1Hz; if we ever
  want raycast-conditioned planning, that's a different observation
  channel for a different model.

- **Bearings are degrees, signed, relative to the car's heading.**
  Positive = right (clockwise), negative = left, range (-180, 180].
  This matches how humans describe relative direction ("turn 30° right").

- **Speeds are km/h.** Distances are metres. These are the units a
  driver would speak in.

Example output::

    speed: 80 km/h
    heading: 45 deg
    surface: gravel
    off_track: no
    edge_left: 5.2 m
    edge_right: 4.8 m
    checkpoint[1]: dist=120 m, bearing=15 deg
    checkpoint[2]: dist=180 m, bearing=-30 deg
    checkpoint[3]: dist=240 m, bearing=20 deg
    opponent[1]: dist=45 m, bearing=-90 deg, rel_speed=10 km/h
    opponent[2]: none
"""

from __future__ import annotations

import math
from typing import List, Tuple

from app.bot_runtime.types import BotGameState, BotOpponent


_NUM_CHECKPOINT_SLOTS = 3
_NUM_OPPONENT_SLOTS = 2

_MS_TO_KMH = 3.6


def format_observation(state: BotGameState) -> str:
    """Render a BotGameState as a compact text observation.

    Pure function. Stable line count regardless of how many checkpoints
    remain or opponents are visible.
    """
    lines: List[str] = []

    speed_kmh = state.car.speed * _MS_TO_KMH
    heading_deg = _wrap_signed_deg(math.degrees(state.car.heading))

    lines.append(f"speed: {speed_kmh:.0f} km/h")
    lines.append(f"heading: {heading_deg:.0f} deg")
    lines.append(f"surface: {state.car.current_surface}")
    lines.append(f"off_track: {'yes' if state.car.off_track else 'no'}")
    lines.append(f"edge_left: {state.track.distance_to_boundary_left:.1f} m")
    lines.append(f"edge_right: {state.track.distance_to_boundary_right:.1f} m")

    for idx, line in enumerate(_format_checkpoints(state), start=1):
        lines.append(f"checkpoint[{idx}]: {line}")

    for idx, line in enumerate(_format_opponents(state.opponents), start=1):
        lines.append(f"opponent[{idx}]: {line}")

    return "\n".join(lines)


def _format_checkpoints(state: BotGameState) -> List[str]:
    """Return exactly _NUM_CHECKPOINT_SLOTS lines describing upcoming checkpoints."""
    checkpoints = state.track.checkpoints
    next_idx = state.track.next_checkpoint
    car_x, car_y = state.car.position
    heading_rad = state.car.heading

    out: List[str] = []
    for offset in range(_NUM_CHECKPOINT_SLOTS):
        target = next_idx + offset
        if target >= len(checkpoints):
            out.append("none")
            continue
        cx, cy = checkpoints[target]
        dist, bearing_deg = _polar_relative_to(car_x, car_y, heading_rad, cx, cy)
        out.append(f"dist={dist:.0f} m, bearing={bearing_deg:.0f} deg")
    return out


def _format_opponents(opponents: List[BotOpponent]) -> List[str]:
    """Return exactly _NUM_OPPONENT_SLOTS lines for the nearest opponents.

    We trust ``BotOpponent.distance`` and ``BotOpponent.relative_angle``
    (already car-relative) but compute relative speed ourselves to keep
    the formatter self-contained.
    """
    nearest = sorted(opponents, key=lambda o: o.distance)[:_NUM_OPPONENT_SLOTS]

    out: List[str] = []
    for opp in nearest:
        bearing_deg = _wrap_signed_deg(math.degrees(opp.relative_angle))
        rel_speed_kmh = math.hypot(opp.velocity[0], opp.velocity[1]) * _MS_TO_KMH
        out.append(
            f"dist={opp.distance:.0f} m, bearing={bearing_deg:.0f} deg, "
            f"rel_speed={rel_speed_kmh:.0f} km/h"
        )
    # Pad with "none" so total slot count is fixed
    while len(out) < _NUM_OPPONENT_SLOTS:
        out.append("none")
    return out


def _polar_relative_to(
    car_x: float,
    car_y: float,
    car_heading_rad: float,
    target_x: float,
    target_y: float,
) -> Tuple[float, float]:
    """Return (distance_m, bearing_deg) of (target_x, target_y) seen from the car.

    Bearing is signed degrees, positive = right of heading (clockwise),
    chosen to match driver intuition ("turn right" = positive). Because
    the game uses standard math y-up coordinates (BotCarState heading
    0 = +x, π/2 = +y), atan2 produces a counter-clockwise angle from
    +x, so we negate the relative angle to flip the rotation direction.
    """
    dx = target_x - car_x
    dy = target_y - car_y
    dist = math.hypot(dx, dy)
    absolute_angle = math.atan2(dy, dx)
    relative_rad = car_heading_rad - absolute_angle  # flip: CCW math -> CW bearing
    bearing_deg = _wrap_signed_deg(math.degrees(relative_rad))
    return dist, bearing_deg


def _wrap_signed_deg(deg: float) -> float:
    """Wrap an angle in degrees to (-180, 180]."""
    wrapped = (deg + 180.0) % 360.0 - 180.0
    # Python's mod yields exact -180 for 180; nudge to the open convention.
    if wrapped == -180.0:
        return 180.0
    return wrapped
