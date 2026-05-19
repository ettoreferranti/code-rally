"""Unit tests for the deterministic controller (issue #154).

The controller is the only thing the engine sees at the 20Hz tick, so
its contract is tight: never raise, always emit something sensible, be
deterministic, and degrade gracefully when the strategist is silent or
the track data is missing.
"""

import math
from typing import List, Optional, Tuple

import pytest

from app.agents.controller import Controller, ControlInputs
from app.agents.intent import Intent
from app.bot_runtime.types import (
    BotCarState,
    BotGameState,
    BotRaceState,
    BotTrackState,
)


# ===== Helpers =====


def _car(
    position: Tuple[float, float] = (0.0, 0.0),
    heading: float = 0.0,
    speed: float = 0.0,  # engine units/s (multiply by _UNITS_TO_KMH=0.6 for km/h)
) -> BotCarState:
    return BotCarState(
        position=position,
        heading=heading,
        speed=speed,
        velocity=(speed * math.cos(heading), speed * math.sin(heading)),
        angular_velocity=0.0,
        health=100.0,
        nitro_charges=3,
        nitro_active=False,
        current_surface="asphalt",
        off_track=False,
    )


def _state(
    car: Optional[BotCarState] = None,
    checkpoints: Optional[List[Tuple[float, float]]] = None,
    next_checkpoint: int = 0,
) -> BotGameState:
    return BotGameState(
        car=car if car is not None else _car(),
        track=BotTrackState(
            checkpoints=checkpoints if checkpoints is not None else [(100.0, 0.0)],
            next_checkpoint=next_checkpoint,
            distance_to_boundary_left=5.0,
            distance_to_boundary_right=5.0,
            upcoming_surface="asphalt",
            upcoming_turn="straight",
            turn_sharpness=0.0,
        ),
        rays=[],
        opponents=[],
        race=BotRaceState(
            current_checkpoint=0,
            total_checkpoints=10,
            position=1,
            total_cars=1,
            elapsed_time=0.0,
            distance_to_finish=100.0,
        ),
    )


def _intent(
    target_speed_kmh: float = 80.0,
    racing_line_offset_m: float = 0.0,
    aggression: float = 0.5,
) -> Intent:
    return Intent(
        target_speed_kmh=target_speed_kmh,
        racing_line_offset_m=racing_line_offset_m,
        aggression=aggression,
    )


# ===== Steering =====


class TestSteering:
    def test_checkpoint_dead_ahead_no_turn(self):
        ctrl = Controller()
        state = _state(
            car=_car(position=(0.0, 0.0), heading=0.0),
            checkpoints=[(100.0, 0.0)],
        )
        out = ctrl.compute(_intent(), state)
        assert not out.turn_left
        assert not out.turn_right

    # NOTE: "checkpoint left" / "checkpoint right" cases moved into
    # `TestSteeringYDownConvention` below (#164) — the prior versions
    # were written assuming y-up math and contradicted the engine's
    # actual y-down convention.

    def test_racing_line_offset_shifts_lookahead_across_track(self):
        # Both car and checkpoint on the +x axis; with zero offset, no turn.
        # In y-down, a positive racing_line_offset shifts the lookahead to
        # the right of track direction = +y in engine coords = "below on
        # screen" = right of a +x-facing driver, so the car should turn right.
        ctrl_a = Controller()
        ctrl_b = Controller()
        state = _state(
            car=_car(position=(0.0, 0.0), heading=0.0),
            checkpoints=[(100.0, 0.0)],
        )
        no_offset = ctrl_a.compute(_intent(racing_line_offset_m=0.0), state)
        with_offset = ctrl_b.compute(_intent(racing_line_offset_m=10.0), state)

        assert not no_offset.turn_left and not no_offset.turn_right
        assert with_offset.turn_right and not with_offset.turn_left

    def test_negative_offset_steers_left(self):
        ctrl = Controller()
        state = _state(
            car=_car(position=(0.0, 0.0), heading=0.0),
            checkpoints=[(100.0, 0.0)],
        )
        out = ctrl.compute(_intent(racing_line_offset_m=-10.0), state)
        assert out.turn_left and not out.turn_right

    def test_no_checkpoint_does_not_turn(self):
        ctrl = Controller()
        state = _state(
            car=_car(position=(0.0, 0.0), heading=0.0),
            checkpoints=[],
            next_checkpoint=0,
        )
        out = ctrl.compute(_intent(), state)
        assert not out.turn_left and not out.turn_right


class TestSteeringYDownConvention:
    """Engine reality: this game uses a y-DOWN coordinate system.

    - Renderer applies `ctx.rotate(heading)` to canvas, where positive
      angles rotate clockwise visually because canvas y is down.
    - Engine maps human "right arrow" to `turn_direction=+1` which sets
      `heading += turn_rate*dt`. Increasing heading therefore rotates
      the car visually to the **right** (CW on screen). For this to be
      consistent with driver intuition, "right of a +x-facing driver"
      must mean **+y** in engine coords (downward on screen), and
      "left" means **-y**.

    The controller's bearing convention must match: target at +y from a
    +x-facing driver → positive bearing → "turn right". Tests below pin
    that down (and would fail under a y-up assumption, see #164).
    """

    def test_checkpoint_below_screen_steers_right(self):
        # Car at origin facing +x; checkpoint at (0, +100), which in this
        # engine is "below" on screen = "right of driver". Expect right turn.
        ctrl = Controller()
        state = _state(
            car=_car(position=(0.0, 0.0), heading=0.0),
            checkpoints=[(0.0, 100.0)],
        )
        out = ctrl.compute(_intent(), state)
        assert out.turn_right and not out.turn_left

    def test_checkpoint_above_screen_steers_left(self):
        # Checkpoint at (0, -100) = above on screen = left of driver.
        ctrl = Controller()
        state = _state(
            car=_car(position=(0.0, 0.0), heading=0.0),
            checkpoints=[(0.0, -100.0)],
        )
        out = ctrl.compute(_intent(), state)
        assert out.turn_left and not out.turn_right


# ===== Speed control =====


class TestSpeed:
    def test_below_target_accelerates(self):
        ctrl = Controller()
        state = _state(car=_car(speed=10.0))  # 6 km/h displayed
        out = ctrl.compute(_intent(target_speed_kmh=80.0), state)
        assert out.accelerate and not out.brake

    def test_above_target_brakes(self):
        ctrl = Controller()
        # speed=100 units/s = 60 km/h displayed (> 50 km/h target → brake).
        state = _state(car=_car(speed=100.0))
        out = ctrl.compute(_intent(target_speed_kmh=50.0), state)
        assert out.brake and not out.accelerate

    def test_within_deadband_coasts(self):
        ctrl = Controller()
        # Aggression 0 → wider deadband (4 km/h). 80 km/h ± 3 km/h is coast.
        # 80 km/h displayed = 80 / 0.6 ≈ 133.33 units/s.
        state = _state(car=_car(speed=80.0 / 0.6))
        out = ctrl.compute(_intent(target_speed_kmh=80.0, aggression=0.0), state)
        assert not out.accelerate and not out.brake

    def test_target_speed_zero_brakes_when_moving(self):
        ctrl = Controller()
        state = _state(car=_car(speed=20.0))
        out = ctrl.compute(_intent(target_speed_kmh=0.0), state)
        assert out.brake

    def test_target_150_kmh_resolves_to_realistic_engine_speed(self):
        """Calibration regression for #166: at target 150 km/h, the
        controller wants the car at 150/0.6 = 250 units/s — which is
        83% of MAX_SPEED, i.e. visually fast. Under the old (wrong)
        3.6 conversion the same intent only asked for 42 units/s.
        """
        ctrl = Controller()
        # Car already at 250 units/s should COAST (within 4 km/h deadband)
        # because curr = 250 * 0.6 = 150 km/h matches target exactly.
        state = _state(car=_car(speed=250.0))
        out = ctrl.compute(_intent(target_speed_kmh=150.0, aggression=0.0), state)
        assert not out.accelerate and not out.brake


class TestSpeedAnticipation:
    """The controller projects speed forward by `speed_horizon_ticks` and
    switches accel/brake on the projected error. This smooths the prior
    bang-bang oscillation (observed: ±40 km/h around target).

    Strategy: same bool output (engine constraint), but trigger the
    state change earlier when the current trend already commits to
    crossing target. Falls back to plain error on the first tick.
    """

    def test_brakes_early_when_speed_rising_toward_target(self):
        # Speed rose from 228 → 240 units/s between ticks (136.8 → 144 km/h,
        # rate ≈ 7.2 km/h/tick — close to the engine's full-accel rate).
        # Current 144 is still 6 below the 150 target, but the 1.5-tick
        # projection clears target+deadband(3 at agg=0.5) at 154.8 km/h.
        # Without anticipation, this tick would still accelerate; with
        # anticipation, we brake before the inevitable overshoot.
        ctrl = Controller(speed_horizon_ticks=1.5)
        ctrl.compute(_intent(target_speed_kmh=150.0),
                     _state(car=_car(speed=228.0)))
        out = ctrl.compute(_intent(target_speed_kmh=150.0),
                           _state(car=_car(speed=240.0)))
        assert out.brake and not out.accelerate

    def test_keeps_accelerating_when_speed_falling_below_target(self):
        # Falling: 260 → 240 (156 → 144 km/h, rate = −12 km/h/tick). Current
        # 144 is only 6 below target, but the falling trend projects to 126
        # → well below target → accelerate.
        ctrl = Controller(speed_horizon_ticks=1.5)
        ctrl.compute(_intent(target_speed_kmh=150.0),
                     _state(car=_car(speed=260.0)))
        out = ctrl.compute(_intent(target_speed_kmh=150.0),
                           _state(car=_car(speed=240.0)))
        assert out.accelerate and not out.brake

    def test_steady_at_target_coasts(self):
        # Speed stable at 150 km/h (250 units/s) across two calls.
        # Projection = current, delta=0, coast.
        ctrl = Controller(speed_horizon_ticks=1.5)
        ctrl.compute(_intent(target_speed_kmh=150.0, aggression=0.0),
                     _state(car=_car(speed=250.0)))
        out = ctrl.compute(_intent(target_speed_kmh=150.0, aggression=0.0),
                           _state(car=_car(speed=250.0)))
        assert not out.accelerate and not out.brake

    def test_first_call_falls_back_to_plain_error(self):
        # No previous speed yet → must behave like the old bang-bang.
        # 100 units/s = 60 km/h, target=150 → accelerate.
        ctrl = Controller(speed_horizon_ticks=1.5)
        out = ctrl.compute(_intent(target_speed_kmh=150.0, aggression=0.0),
                           _state(car=_car(speed=100.0)))
        assert out.accelerate and not out.brake


# ===== Fallback behaviour =====


class TestFallback:
    def test_none_intent_with_no_history_does_not_raise(self):
        ctrl = Controller()
        state = _state(car=_car(speed=0.0))
        out = ctrl.compute(None, state)
        # Stationary + fallback cruise speed > 0 → should accelerate
        assert isinstance(out, ControlInputs)
        assert out.accelerate

    def test_none_intent_holds_last_intent(self):
        ctrl = Controller()
        state = _state(car=_car(speed=0.0))
        first = ctrl.compute(_intent(target_speed_kmh=100.0), state)
        held = ctrl.compute(None, state)
        # Both ticks see speed 0; both should accelerate toward 100 km/h
        assert first.accelerate == held.accelerate == True

    def test_intent_replaces_held_intent(self):
        ctrl = Controller()
        # speed=200 units/s = 120 km/h displayed.
        state = _state(car=_car(speed=200.0))
        # Hold an intent that says target=100 → at 120, would brake.
        first = ctrl.compute(_intent(target_speed_kmh=100.0), state)
        assert first.brake
        # Now strategist returns a new intent with target=150 → should accelerate.
        new = ctrl.compute(_intent(target_speed_kmh=150.0), state)
        assert new.accelerate and not new.brake


# ===== Robustness =====


class TestRobustness:
    def test_extreme_intent_does_not_raise(self):
        ctrl = Controller()
        state = _state()
        # Intent schema already clamps; we just verify the controller
        # tolerates the schema's bounds without raising.
        out = ctrl.compute(
            Intent(target_speed_kmh=400.0, racing_line_offset_m=20.0, aggression=1.0),
            state,
        )
        assert isinstance(out, ControlInputs)

    def test_deterministic_given_same_inputs(self):
        ctrl_a = Controller()
        ctrl_b = Controller()
        state = _state(
            car=_car(position=(10.0, 5.0), heading=0.3, speed=15.0),
            checkpoints=[(100.0, 30.0), (200.0, 60.0)],
            next_checkpoint=0,
        )
        intent = _intent(target_speed_kmh=90.0, racing_line_offset_m=2.0, aggression=0.4)
        assert ctrl_a.compute(intent, state) == ctrl_b.compute(intent, state)

    def test_aggression_one_or_zero_does_not_crash(self):
        ctrl = Controller()
        state = _state(car=_car(speed=10.0))
        for aggr in (0.0, 1.0):
            out = ctrl.compute(_intent(aggression=aggr), state)
            assert isinstance(out, ControlInputs)

    def test_perf_under_1ms(self):
        """Compute is synchronous and trivial; sanity-check the per-tick budget."""
        import time

        ctrl = Controller()
        state = _state(
            car=_car(position=(10.0, 5.0), heading=0.3, speed=15.0),
            checkpoints=[(100.0, 30.0), (200.0, 60.0), (300.0, 90.0)],
        )
        intent = _intent()

        # Run 1000 iterations and average; absolute threshold is generous to
        # avoid CI flakiness, the real budget is 50ms/tick at 20Hz.
        start = time.perf_counter()
        for _ in range(1000):
            ctrl.compute(intent, state)
        elapsed = time.perf_counter() - start
        per_call_ms = (elapsed / 1000) * 1000
        assert per_call_ms < 1.0, f"controller too slow: {per_call_ms:.3f} ms/call"
