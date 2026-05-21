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

# Distance (engine units, ≈ metres) at which the lookahead starts
# blending from cp[next] toward cp[next+1]. When the car is further than
# this from cp[next], the lookahead sits exactly on cp[next] (legacy
# single-checkpoint behaviour). Inside the radius, the lookahead smoothly
# slides forward, which is what gives the controller racing-line geometry
# (the steering target anticipates the corner exit, not just the apex
# marker).
_LOOKAHEAD_BLEND_RADIUS_M = 60.0

# Lateral offset magnitudes applied when a tactic is active. These
# override the LLM-supplied ``racing_line_offset_m`` so the tactic enum
# is actually load-bearing. Tuned to be close to (but not at) the
# Intent schema ceiling (±20 m) — the racing line lives within the
# track, and 8 m / 6 m is comfortably inside most stage widths.
_TACTIC_ATTACK_OFFSET_M = 8.0  # overtake / pit
_TACTIC_BLOCK_OFFSET_M = 6.0  # defensive inside line


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
        speed_horizon_ticks: float = 1.5,
    ) -> None:
        self._fallback_speed_kmh = fallback_speed_kmh
        self._base_steer_deadband_deg = base_steer_deadband_deg
        self._base_speed_deadband_kmh = base_speed_deadband_kmh
        # Anticipation horizon for the speed PD controller. The controller
        # projects current_kmh forward by this many bot ticks using the
        # measured rate of change, then switches accel/brake on the
        # projected error. Default 1.5 (≈75 ms at 20 Hz bot tick) — enough
        # to brake before the car blows past target, small enough to avoid
        # introducing the opposite oscillation.
        self._speed_horizon_ticks = speed_horizon_ticks
        self._last_intent: Optional[Intent] = None
        # Tick counter for throttled diagnostic logging (#162).
        self._tick_count: int = 0
        # Previous km/h reading, used to estimate the speed rate-of-change
        # for the projection above. None on the first call → fall back to
        # plain bang-bang (no projection yet).
        self._prev_speed_kmh: Optional[float] = None

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
                use_nitro=False,
                state=state,
            )
            self._maybe_log(state, self._fallback_speed_kmh, 0.0, 0.0, inputs, fallback=True)
            return inputs

        target = _clamp(effective.target_speed_kmh, 0.0, _MAX_TARGET_SPEED_KMH)
        aggression = _clamp(effective.aggression, 0.0, 1.0)
        offset = _resolve_offset(effective, state)
        offset = _clamp(offset, -_MAX_OFFSET_M, _MAX_OFFSET_M)
        # Nitro is gated on having charges available; the engine respects
        # this too but we surface the gate here so the controller's per-tick
        # output reflects reality (the LLM's intent.use_nitro can be True
        # for many ticks while charges trickle down to zero).
        use_nitro = bool(effective.use_nitro) and state.car.nitro_charges > 0
        inputs = self._compute_from_target(
            target_speed_kmh=target,
            racing_line_offset_m=offset,
            aggression=aggression,
            use_nitro=use_nitro,
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
        tactic_suffix = ""
        if self._last_intent is not None and self._last_intent.tactic != "race":
            target_str = (
                f"#{self._last_intent.target_opponent_index}"
                if self._last_intent.target_opponent_index is not None
                else "-"
            )
            tactic_suffix = f" | tactic={self._last_intent.tactic} target={target_str}"
        logger.debug(
            "controller@(%6.1f,%6.1f) heading=%+5.1f deg | target=%5.1f curr=%5.1f delta=%+6.1f km/h "
            "| offset=%+4.1f m agg=%.2f | accel=%d brake=%d steer=%s nitro=%d | surface=%s off_track=%s%s%s",
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
            int(inputs.nitro),
            state.car.current_surface,
            "Y" if state.car.off_track else "N",
            tactic_suffix,
            " [fallback]" if fallback else "",
        )

    # ----- internals -----

    def _compute_from_target(
        self,
        target_speed_kmh: float,
        racing_line_offset_m: float,
        aggression: float,
        use_nitro: bool,
        state: BotGameState,
    ) -> ControlInputs:
        steer = self._compute_steering(racing_line_offset_m, aggression, state)
        accel, brake = self._compute_speed(target_speed_kmh, aggression, state)
        return ControlInputs(
            accelerate=accel,
            brake=brake,
            turn_left=steer == "left",
            turn_right=steer == "right",
            nitro=use_nitro,
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
        """Return (accelerate, brake) bool pair.

        Uses a one-step finite-difference predictor: project current_kmh
        forward by ``speed_horizon_ticks`` using the rate of change since
        the previous tick, then switch on the projected error. The engine
        only accepts bool flags, so we keep the bang-bang output — but
        decide *when* to flip on anticipated error, not current error.
        That collapses the prior ±40 km/h oscillation around target.
        """
        current_kmh = state.car.speed * _UNITS_TO_KMH

        if self._prev_speed_kmh is not None:
            rate_per_tick = current_kmh - self._prev_speed_kmh
            projected_kmh = current_kmh + rate_per_tick * self._speed_horizon_ticks
        else:
            # First tick (no rate yet): fall back to plain bang-bang.
            projected_kmh = current_kmh
        self._prev_speed_kmh = current_kmh

        deadband = self._base_speed_deadband_kmh * (1.0 - 0.5 * aggression)
        delta = target_speed_kmh - projected_kmh

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
        """Two-checkpoint blended lookahead with perpendicular offset.

        When the car is more than ``_LOOKAHEAD_BLEND_RADIUS_M`` from
        ``cp[next]``, the lookahead sits on ``cp[next]`` (legacy single-
        checkpoint behaviour). Inside the blend radius, the lookahead
        slides forward toward ``cp[next+1]`` — which is what gives the
        controller the geometric anticipation needed to actually drive a
        racing line through a corner, instead of always aiming at the
        next checkpoint marker.

        The perpendicular offset is applied along the local racing-line
        direction (``cp[next] → cp[next+1]`` when available), so a
        constant ``racing_line_offset_m`` is interpreted in the frame of
        the road through the corner, not the frame of the car's current
        approach vector.

        Returns ``None`` when no checkpoint is available.
        """
        checkpoints = state.track.checkpoints
        idx = state.track.next_checkpoint
        if idx < 0 or idx >= len(checkpoints):
            return None

        car_x, car_y = state.car.position
        cp_next = checkpoints[idx]

        has_next_next = idx + 1 < len(checkpoints)
        if has_next_next:
            cp_after = checkpoints[idx + 1]
            d_to_next = math.hypot(cp_next[0] - car_x, cp_next[1] - car_y)
            # weight=0 when far (use cp[next]); weight=1 when arriving at
            # cp[next] (use cp[next+1]).
            weight = max(0.0, min(1.0, 1.0 - d_to_next / _LOOKAHEAD_BLEND_RADIUS_M))
            target_x = (1.0 - weight) * cp_next[0] + weight * cp_after[0]
            target_y = (1.0 - weight) * cp_next[1] + weight * cp_after[1]
            # Local racing-line direction = direction of travel through the
            # corner. Falls back to car→cp[next] if the two checkpoints
            # coincide (degenerate).
            dx = cp_after[0] - cp_next[0]
            dy = cp_after[1] - cp_next[1]
            if dx == 0.0 and dy == 0.0:
                dx = cp_next[0] - car_x
                dy = cp_next[1] - car_y
        else:
            target_x, target_y = cp_next
            dx = cp_next[0] - car_x
            dy = cp_next[1] - car_y

        norm = math.hypot(dx, dy)
        if norm == 0.0:
            return target_x, target_y
        ux, uy = dx / norm, dy / norm

        # Right perpendicular in y-DOWN coords (#164): rotating a track-
        # direction vector CW on screen yields the "right of track" side.
        # In math terms that's a CCW rotation since canvas y is flipped:
        #     rot_+90(ux, uy) = (-uy, ux)
        # Positive offset shifts the lookahead to the right of track direction.
        px, py = -uy, ux
        return (target_x + racing_line_offset_m * px, target_y + racing_line_offset_m * py)


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


def _resolve_offset(intent: Intent, state: BotGameState) -> float:
    """Convert ``intent.tactic`` + ``target_opponent_index`` to an effective
    lateral offset, falling back to the LLM-supplied
    ``racing_line_offset_m`` when no tactical override applies.

    Resolution order:

    1. ``tactic="overtake"`` with a visible target ⇒ shift to the open
       side of that opponent (sign opposite the opponent's relative
       bearing).
    2. ``tactic="pit"`` with a visible target ⇒ shift toward the
       opponent (sign matches the opponent's relative bearing).
    3. ``tactic="block"`` with a known upcoming turn ⇒ shift to the
       inside of the turn (positive offset for a right turn,
       negative for a left turn).
    4. Otherwise ⇒ use ``intent.racing_line_offset_m`` verbatim.

    "Visible target" means the opponent at the indexed slot exists in
    the nearest-2 sorted list (matching what the observation showed the
    LLM). If the slot is empty (e.g. the LLM hallucinates a target in a
    solo race), the offset falls through to the LLM value rather than
    overriding it.
    """
    tactic = intent.tactic
    if tactic in ("overtake", "pit") and intent.target_opponent_index is not None:
        target = _opponent_at_slot(state, intent.target_opponent_index)
        if target is not None:
            # In y-down, positive bearing = opponent on the driver's right.
            # Overtake = go to the OPPOSITE side (negative offset = left of
            # track direction). Pit = aim AT the opponent.
            sign = 1.0 if target.relative_angle >= 0 else -1.0
            if tactic == "overtake":
                return -sign * _TACTIC_ATTACK_OFFSET_M
            return sign * _TACTIC_ATTACK_OFFSET_M  # pit
    if tactic == "block":
        upcoming = state.track.upcoming_turn
        if upcoming == "right":
            # Inside of a right turn is on the driver's right ⇒ +y in
            # y-down ⇒ positive offset.
            return _TACTIC_BLOCK_OFFSET_M
        if upcoming == "left":
            return -_TACTIC_BLOCK_OFFSET_M
        # "straight" or unknown — block has no inside line to claim.

    return float(intent.racing_line_offset_m)


def _opponent_at_slot(state: BotGameState, slot_index: int):
    """Return the opponent at the given observation slot, or ``None``.

    The observation sorts opponents by distance and exposes the two
    nearest as slots 0 and 1. The controller uses the same ordering so
    the LLM's ``target_opponent_index`` references the same car the
    observation showed it.
    """
    if not state.opponents:
        return None
    nearest = sorted(state.opponents, key=lambda o: o.distance)[:2]
    if 0 <= slot_index < len(nearest):
        return nearest[slot_index]
    return None
