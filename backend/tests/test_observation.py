"""Unit tests for the observation formatter (issue #153).

The formatter is the single most iterated-on surface in the LLM agent
system. These tests pin down the format (golden output), the bearing
sign convention (driver-intuitive: right = positive), unit conversions,
solo-race behaviour, opponent ordering, and the fixed-slot guarantee
that keeps prompt size stable.
"""

import math
from typing import List, Optional, Tuple

import pytest

from app.agents.observation import (
    _polar_relative_to,
    _wrap_signed_deg,
    format_observation,
)
from app.bot_runtime.types import (
    BotCarState,
    BotGameState,
    BotOpponent,
    BotRaceState,
    BotRaycast,
    BotTrackState,
)


# ===== Helpers =====


def _car(
    position: Tuple[float, float] = (0.0, 0.0),
    heading: float = 0.0,
    speed: float = 0.0,
    surface: str = "asphalt",
    off_track: bool = False,
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
        current_surface=surface,
        off_track=off_track,
    )


def _track(
    checkpoints: Optional[List[Tuple[float, float]]] = None,
    next_checkpoint: int = 0,
    edge_left: float = 5.0,
    edge_right: float = 5.0,
) -> BotTrackState:
    return BotTrackState(
        checkpoints=checkpoints if checkpoints is not None else [],
        next_checkpoint=next_checkpoint,
        distance_to_boundary_left=edge_left,
        distance_to_boundary_right=edge_right,
        upcoming_surface="asphalt",
        upcoming_turn="straight",
        turn_sharpness=0.0,
    )


def _opponent(
    position: Tuple[float, float],
    velocity: Tuple[float, float] = (0.0, 0.0),
    heading: float = 0.0,
    distance: float = 0.0,
    relative_angle: float = 0.0,
) -> BotOpponent:
    return BotOpponent(
        position=position,
        velocity=velocity,
        heading=heading,
        distance=distance,
        relative_angle=relative_angle,
    )


def _state(
    car: Optional[BotCarState] = None,
    track: Optional[BotTrackState] = None,
    opponents: Optional[List[BotOpponent]] = None,
    rays: Optional[List[BotRaycast]] = None,
) -> BotGameState:
    return BotGameState(
        car=car if car is not None else _car(),
        track=track if track is not None else _track(),
        rays=rays if rays is not None else [],
        opponents=opponents if opponents is not None else [],
        race=BotRaceState(
            current_checkpoint=0,
            total_checkpoints=10,
            position=1,
            total_cars=1,
            elapsed_time=0.0,
            distance_to_finish=100.0,
        ),
    )


# ===== Bearing-sign convention (the part future-me must not get wrong) =====


class TestBearingConvention:
    """Lock down positive = right (clockwise) from the car's heading."""

    def test_target_directly_ahead_is_zero_bearing(self):
        # Car at origin facing +x; target on +x axis.
        _, bearing = _polar_relative_to(0, 0, 0.0, 50.0, 0.0)
        assert bearing == pytest.approx(0.0, abs=1e-6)

    def test_target_to_the_right_is_positive_bearing(self):
        # Engine uses y-DOWN coords (#164): "right of a +x-facing driver"
        # is +y in engine coords. Bearing should be +90.
        _, bearing = _polar_relative_to(0, 0, 0.0, 0.0, 50.0)
        assert bearing == pytest.approx(90.0, abs=1e-6)

    def test_target_to_the_left_is_negative_bearing(self):
        # In y-down, target at -y is above on screen = left of driver.
        _, bearing = _polar_relative_to(0, 0, 0.0, 0.0, -50.0)
        assert bearing == pytest.approx(-90.0, abs=1e-6)

    def test_target_behind_is_180(self):
        _, bearing = _polar_relative_to(0, 0, 0.0, -50.0, 0.0)
        # Either +180 or -180 is fine mathematically; we anchor to +180.
        assert bearing == pytest.approx(180.0, abs=1e-6)


class TestWrapSignedDeg:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            (0.0, 0.0),
            (90.0, 90.0),
            (180.0, 180.0),
            (-180.0, 180.0),
            (181.0, -179.0),
            (-181.0, 179.0),
            (360.0, 0.0),
            (450.0, 90.0),
            (-450.0, -90.0),
        ],
    )
    def test_wraps_to_open_minus_180_180(self, raw, expected):
        assert _wrap_signed_deg(raw) == pytest.approx(expected, abs=1e-9)


# ===== Format / golden output =====


class TestFormatGolden:
    def test_full_observation_matches_expected_lines(self):
        # Calibration: 20 units/s × 0.6 = 12 km/h displayed (see #166).
        state = _state(
            car=_car(
                position=(0.0, 0.0),
                heading=0.0,
                speed=20.0,  # 12 km/h displayed
                surface="gravel",
            ),
            track=_track(
                checkpoints=[(100.0, 0.0), (200.0, 0.0), (300.0, 0.0)],
                next_checkpoint=0,
                edge_left=5.2,
                edge_right=4.8,
            ),
            opponents=[
                _opponent(
                    position=(50.0, 0.0),
                    velocity=(10.0, 0.0),  # 6 km/h
                    distance=50.0,
                    relative_angle=0.0,
                )
            ],
        )

        out = format_observation(state)
        lines = out.split("\n")
        assert lines == [
            "speed: 12 km/h",
            "heading: 0 deg",
            "surface: gravel",
            "off_track: no",
            "edge_left: 5.2 m",
            "edge_right: 4.8 m",
            "checkpoint[1]: dist=100 m, bearing=0 deg",
            "checkpoint[2]: dist=200 m, bearing=0 deg",
            "checkpoint[3]: dist=300 m, bearing=0 deg",
            "opponent[1]: dist=50 m, bearing=0 deg, rel_speed=6 km/h",
            "opponent[2]: none",
        ]

    def test_off_track_yes(self):
        state = _state(car=_car(off_track=True))
        assert "off_track: yes" in format_observation(state)

    def test_surface_field_reflects_state(self):
        for surface in ("asphalt", "gravel", "ice", "wet"):
            out = format_observation(_state(car=_car(surface=surface)))
            assert f"surface: {surface}" in out


# ===== Stability: fixed slot count =====


class TestSlotStability:
    def test_solo_race_has_no_opponent_lines_but_padded_slots(self):
        state = _state(opponents=[])
        out = format_observation(state)
        assert "opponent[1]: none" in out
        assert "opponent[2]: none" in out
        # Total line count fixed regardless of opponent count
        assert len(out.split("\n")) == 11

    def test_fewer_than_three_remaining_checkpoints_pads_with_none(self):
        state = _state(
            track=_track(checkpoints=[(100.0, 0.0)], next_checkpoint=0)
        )
        out = format_observation(state)
        assert "checkpoint[1]: dist=100 m, bearing=0 deg" in out
        assert "checkpoint[2]: none" in out
        assert "checkpoint[3]: none" in out

    def test_more_than_two_opponents_keeps_two_nearest(self):
        opponents = [
            _opponent(position=(100.0, 0.0), distance=100.0, relative_angle=0.0),
            _opponent(position=(50.0, 0.0), distance=50.0, relative_angle=0.0),
            _opponent(position=(20.0, 0.0), distance=20.0, relative_angle=0.0),
        ]
        out = format_observation(_state(opponents=opponents))
        # Two nearest are distance 20 and 50; 100 must not appear in opponent slots
        assert "opponent[1]: dist=20" in out
        assert "opponent[2]: dist=50" in out
        # The third opponent's distance shouldn't show up
        assert "opponent[3]" not in out
        assert "dist=100" not in out

    def test_line_count_invariant_across_states(self):
        a = format_observation(_state())
        b = format_observation(
            _state(
                track=_track(checkpoints=[(1, 1), (2, 2)], next_checkpoint=0),
                opponents=[
                    _opponent((10, 0), distance=10, relative_angle=0),
                    _opponent((20, 0), distance=20, relative_angle=0),
                    _opponent((30, 0), distance=30, relative_angle=0),
                ],
            )
        )
        assert len(a.split("\n")) == len(b.split("\n"))


# ===== Heading rotates bearings =====


class TestHeadingRotatesBearings:
    def test_rotating_car_heading_changes_checkpoint_bearing(self):
        checkpoints = [(100.0, 0.0)]
        # Car faces +x: checkpoint dead ahead.
        state_a = _state(
            car=_car(position=(0.0, 0.0), heading=0.0),
            track=_track(checkpoints=checkpoints, next_checkpoint=0),
        )
        # Car now faces +y. In y-down (#164) that's "facing down on screen".
        # The checkpoint at +x is to the RIGHT on screen = to the driver's
        # LEFT (since the driver is facing down). Expect -90.
        state_b = _state(
            car=_car(position=(0.0, 0.0), heading=math.pi / 2),
            track=_track(checkpoints=checkpoints, next_checkpoint=0),
        )

        assert "bearing=0 deg" in format_observation(state_a)
        assert "bearing=-90 deg" in format_observation(state_b)


# ===== Pure / deterministic =====


class TestPureFunction:
    def test_same_state_yields_same_output(self):
        state = _state()
        assert format_observation(state) == format_observation(state)

    def test_does_not_mutate_state(self):
        opponents = [_opponent((50, 0), distance=50, relative_angle=0)]
        state = _state(opponents=opponents)
        before_ids = [id(o) for o in opponents]
        _ = format_observation(state)
        after_ids = [id(o) for o in opponents]
        assert before_ids == after_ids  # same objects, same order
