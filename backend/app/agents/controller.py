"""Deterministic 20Hz controller for the LLM agent (issue #154).

Consumes the latest :class:`Intent` produced by the strategist (#152)
and the current :class:`BotGameState` and emits discrete control flags
matching the engine's :class:`PlayerInput` shape.

Three design decisions worth highlighting before changing this file:

1. **Discrete output.** The engine accepts bool flags, not continuous
   steer/throttle/brake. Pure-pursuit gives a continuous steering
   angle which we threshold against a deadband to produce the bool
   turn_left/turn_right flags. The same idea applies on the speed
   axis (accelerate / brake / coast).

2. **Hold-last-intent fallback.** If the strategist hasn't produced an
   Intent yet, or returns None this tick, the controller reuses the
   most recent valid Intent. With no Intent ever, it falls back to a
   slow cruise along the next checkpoint direction. The controller
   must never raise into the per-tick path.

3. **Coordinate convention: y-DOWN (#164).** The engine, physics, and
   renderer all treat positive y as "down on screen". Increasing the
   car heading rotates the car clockwise visually, which matches the
   "right turn" semantics. So a target at **+y** relative to a +x-facing
   driver is to the driver's RIGHT, and bearing > 0 means "turn right".
   This affects both the bearing computation and the rotation used to
   shift the lookahead by ``racing_line_offset_m``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

from app.agents.intent import Intent
from app.bot_runtime.types import BotGameState


_MS_TO_KMH = 3.6

# Hard ceilings independent of the Intent schema's own bounds.
# Defensive only — the schema already clamps, but if someone constructs
# an Intent by other means (or we change the schema later) this keeps
# the controller from emitting nonsense.
_MAX_TARGET_SPEED_KMH = 400.0
_MAX_OFFSET_M = 20.0


@dataclass(frozen=True)
class ControlInputs:
    """Discrete control flags matching the engine's PlayerInput shape."""

    accelerate: bool = False
    brake: bool = False
    turn_left: bool = False
    turn_right: bool = False
    nitro: bool = False


class Controller:
    """Per-car deterministic controller. Hold one instance per LLM-driven car."""

    def __init__(
        self,
        fallback_speed_kmh: float = 30.0,
        base_steer_deadband_deg: float = 4.0,
        base_speed_deadband_kmh: float = 4.0,
    ) -> None:
        self._fallback_speed_kmh = fallback_speed_kmh
        self._base_steer_deadband_deg = base_steer_deadband_deg
        self._base_speed_deadband_kmh = base_speed_deadband_kmh
        self._last_intent: Optional[Intent] = None

    def compute(self, intent: Optional[Intent], state: BotGameState) -> ControlInputs:
        """Compute the next-tick control flags. Never raises."""
        if intent is not None:
            self._last_intent = intent
        effective = intent if intent is not None else self._last_intent

        if effective is None:
            # No Intent has ever arrived — cruise slowly toward the next checkpoint.
            return self._compute_from_target(
                target_speed_kmh=self._fallback_speed_kmh,
                racing_line_offset_m=0.0,
                aggression=0.0,
                state=state,
            )

        return self._compute_from_target(
            target_speed_kmh=_clamp(effective.target_speed_kmh, 0.0, _MAX_TARGET_SPEED_KMH),
            racing_line_offset_m=_clamp(effective.racing_line_offset_m, -_MAX_OFFSET_M, _MAX_OFFSET_M),
            aggression=_clamp(effective.aggression, 0.0, 1.0),
            state=state,
        )

    # ----- internals -----

    def _compute_from_target(
        self,
        target_speed_kmh: float,
        racing_line_offset_m: float,
        aggression: float,
        state: BotGameState,
    ) -> ControlInputs:
        steer = self._compute_steering(racing_line_offset_m, aggression, state)
        accel, brake = self._compute_speed(target_speed_kmh, aggression, state)
        return ControlInputs(
            accelerate=accel,
            brake=brake,
            turn_left=steer == "left",
            turn_right=steer == "right",
        )

    def _compute_steering(
        self,
        racing_line_offset_m: float,
        aggression: float,
        state: BotGameState,
    ) -> str:
        """Return 'left', 'right', or 'straight'."""
        lookahead = self._lookahead_point(racing_line_offset_m, state)
        if lookahead is None:
            return "straight"

        car_x, car_y = state.car.position
        dx = lookahead[0] - car_x
        dy = lookahead[1] - car_y
        if dx == 0.0 and dy == 0.0:
            return "straight"

        absolute_angle = math.atan2(dy, dx)
        # Engine uses y-DOWN coordinates (#164): heading increases CW visually,
        # so "right of driver" corresponds to +y in engine coords. Positive
        # bearing therefore means target is right of heading.
        bearing_deg = math.degrees(absolute_angle - state.car.heading)
        bearing_deg = _wrap_signed_deg(bearing_deg)

        # Aggression tightens the deadband: higher aggression = quicker to turn.
        deadband = self._base_steer_deadband_deg * (1.0 - 0.5 * aggression)
        if bearing_deg > deadband:
            return "right"
        if bearing_deg < -deadband:
            return "left"
        return "straight"

    def _compute_speed(
        self,
        target_speed_kmh: float,
        aggression: float,
        state: BotGameState,
    ) -> tuple:
        """Return (accelerate, brake) bool pair."""
        current_kmh = state.car.speed * _MS_TO_KMH
        deadband = self._base_speed_deadband_kmh * (1.0 - 0.5 * aggression)
        delta = target_speed_kmh - current_kmh

        if delta > deadband:
            return True, False
        if delta < -deadband:
            return False, True
        return False, False

    def _lookahead_point(
        self,
        racing_line_offset_m: float,
        state: BotGameState,
    ) -> Optional[tuple]:
        """Lookahead = next checkpoint + perpendicular offset.

        Returns None when no checkpoint is available (e.g. all passed),
        which the caller treats as "go straight".
        """
        checkpoints = state.track.checkpoints
        idx = state.track.next_checkpoint
        if idx < 0 or idx >= len(checkpoints):
            return None

        cx, cy = checkpoints[idx]
        car_x, car_y = state.car.position

        # Track direction unit vector at the car (approximated as car → checkpoint).
        dx = cx - car_x
        dy = cy - car_y
        norm = math.hypot(dx, dy)
        if norm == 0.0:
            return cx, cy
        ux, uy = dx / norm, dy / norm

        # Right perpendicular in y-DOWN coords (#164): rotating a track-
        # direction vector CW on screen yields the "right of track" side.
        # In math terms that's a CCW rotation since canvas y is flipped:
        #     rot_+90(ux, uy) = (-uy, ux)
        # Positive offset shifts the lookahead to the right of track direction.
        px, py = -uy, ux
        return (cx + racing_line_offset_m * px, cy + racing_line_offset_m * py)


def _clamp(value: float, lo: float, hi: float) -> float:
    if value < lo:
        return lo
    if value > hi:
        return hi
    return value


def _wrap_signed_deg(deg: float) -> float:
    wrapped = (deg + 180.0) % 360.0 - 180.0
    if wrapped == -180.0:
        return 180.0
    return wrapped
