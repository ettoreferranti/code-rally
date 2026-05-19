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

import logging
import math
from dataclasses import dataclass
from typing import Optional

from app.agents.intent import Intent
from app.bot_runtime.types import BotGameState

logger = logging.getLogger(__name__)


# Conversion from engine speed (units/s) to displayed km/h.
# MUST match `frontend/src/components/RaceHUD.tsx` so the LLM and the
# user see the same number on the speedometer (#166). The engine's
# MAX_SPEED is 300 units/s; with this factor that maps to ~180 km/h
# (rally-car top speed).
_UNITS_TO_KMH = 0.6
# Diagnostic logging cadence: emit one info line per ~N controller ticks.
# At the engine's 20Hz bot tick rate this is ~one line every 500 ms per car.
_DIAGNOSTIC_LOG_EVERY = 10

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
        # Tick counter for throttled diagnostic logging (#162).
        self._tick_count: int = 0

    def compute(self, intent: Optional[Intent], state: BotGameState) -> ControlInputs:
        """Compute the next-tick control flags. Never raises."""
        if intent is not None:
            self._last_intent = intent
        effective = intent if intent is not None else self._last_intent

        if effective is None:
            # No Intent has ever arrived — cruise slowly toward the next checkpoint.
            inputs = self._compute_from_target(
                target_speed_kmh=self._fallback_speed_kmh,
                racing_line_offset_m=0.0,
                aggression=0.0,
                state=state,
            )
            self._maybe_log(state, self._fallback_speed_kmh, 0.0, 0.0, inputs, fallback=True)
            return inputs

        target = _clamp(effective.target_speed_kmh, 0.0, _MAX_TARGET_SPEED_KMH)
        offset = _clamp(effective.racing_line_offset_m, -_MAX_OFFSET_M, _MAX_OFFSET_M)
        aggression = _clamp(effective.aggression, 0.0, 1.0)
        inputs = self._compute_from_target(
            target_speed_kmh=target,
            racing_line_offset_m=offset,
            aggression=aggression,
            state=state,
        )
        self._maybe_log(state, target, offset, aggression, inputs, fallback=False)
        return inputs

    def _maybe_log(
        self,
        state: BotGameState,
        target_kmh: float,
        offset_m: float,
        aggression: float,
        inputs: ControlInputs,
        fallback: bool,
    ) -> None:
        """Diagnostic logger for #162. Fires once per ~500 ms per controller.

        Logs at DEBUG level so the line stays out of the default INFO console
        but is one log-level flip away when diagnosing a future regression.
        Enable with `logging.getLogger('app.agents.controller').setLevel('DEBUG')`
        or by lowering the uvicorn log level.
        """
        self._tick_count += 1
        if self._tick_count % _DIAGNOSTIC_LOG_EVERY != 0:
            return
        if not logger.isEnabledFor(logging.DEBUG):
            return
        current_kmh = state.car.speed * _UNITS_TO_KMH
        steer = "L" if inputs.turn_left else ("R" if inputs.turn_right else "-")
        logger.debug(
            "controller@(%6.1f,%6.1f) heading=%+5.1f deg | target=%5.1f curr=%5.1f delta=%+6.1f km/h "
            "| offset=%+4.1f m agg=%.2f | accel=%d brake=%d steer=%s | surface=%s off_track=%s%s",
            state.car.position[0],
            state.car.position[1],
            math.degrees(state.car.heading),
            target_kmh,
            current_kmh,
            target_kmh - current_kmh,
            offset_m,
            aggression,
            int(inputs.accelerate),
            int(inputs.brake),
            steer,
            state.car.current_surface,
            "Y" if state.car.off_track else "N",
            " [fallback]" if fallback else "",
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
        current_kmh = state.car.speed * _UNITS_TO_KMH
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
