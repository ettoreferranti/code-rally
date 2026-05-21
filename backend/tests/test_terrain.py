"""Unit tests for the terrain helpers.

These helpers replace the hardcoded placeholders that used to live in
``bot_manager.py`` (boundary distance, upcoming-turn direction +
sharpness, upcoming-surface lookup) and now power the LLM observation
with real geometry. Tests pin down the conventions:

- Boundary distances are in track-frame: ``left`` is the distance to
  the edge on the LEFT of track-direction (in y-down screen coords),
  ``right`` likewise.
- ``upcoming_turn`` direction is "left" / "right" / "straight"; sign of
  the cross product follows the engine's y-DOWN convention (#164), so
  a road that bends visually right yields ``"right"``.
- ``turn_sharpness`` is 0.0 (straight) to 1.0 (U-turn).
"""

from __future__ import annotations

import math
from typing import List, Tuple

import pytest

from app.core.terrain import (
    boundary_distances,
    upcoming_surface,
    upcoming_turn,
)
from app.core.track import (
    Checkpoint,
    SurfaceType,
    Track,
    TrackPoint,
    TrackSegment,
)


def _seg(
    ax: float,
    ay: float,
    bx: float,
    by: float,
    width: float = 10.0,
    surface: SurfaceType = SurfaceType.ASPHALT,
) -> TrackSegment:
    return TrackSegment(
        start=TrackPoint(x=ax, y=ay, width=width, surface=surface),
        end=TrackPoint(x=bx, y=by, width=width, surface=surface),
    )


def _track(
    segments: List[TrackSegment],
    checkpoints: List[Tuple[float, float]] | None = None,
    start_position: Tuple[float, float] = (0.0, 0.0),
) -> Track:
    cps = [
        Checkpoint(position=p, angle=0.0, width=20.0, index=i)
        for i, p in enumerate(checkpoints or [])
    ]
    return Track(
        segments=segments,
        checkpoints=cps,
        start_position=start_position,
        start_heading=0.0,
        finish_position=(0.0, 0.0),
        finish_heading=0.0,
    )


# ===== Boundary distances =====


class TestBoundaryDistances:
    def test_car_on_centreline_gets_equal_left_and_right(self):
        track = _track([_seg(0, 0, 100, 0, width=10.0)])
        left, right = boundary_distances((50.0, 0.0), track)
        assert left == pytest.approx(5.0, abs=1e-6)
        assert right == pytest.approx(5.0, abs=1e-6)

    def test_y_down_right_of_track_means_more_room_on_left(self):
        # Segment runs +x; in y-DOWN coords (#164), +y is "right of track
        # direction" (visually below the segment on screen). A car at +y
        # should have a SMALLER right-edge distance and a LARGER left-edge
        # distance.
        track = _track([_seg(0, 0, 100, 0, width=10.0)])
        left, right = boundary_distances((50.0, 3.0), track)
        assert left == pytest.approx(8.0, abs=1e-6)
        assert right == pytest.approx(2.0, abs=1e-6)

    def test_y_down_left_of_track_means_more_room_on_right(self):
        track = _track([_seg(0, 0, 100, 0, width=10.0)])
        left, right = boundary_distances((50.0, -4.0), track)
        assert left == pytest.approx(1.0, abs=1e-6)
        assert right == pytest.approx(9.0, abs=1e-6)

    def test_picks_closest_of_multiple_segments(self):
        # Two parallel segments; car is right next to the second one.
        track = _track(
            [
                _seg(0, 0, 100, 0, width=10.0),
                _seg(0, 200, 100, 200, width=10.0),
            ]
        )
        left, right = boundary_distances((50.0, 199.0), track)
        # Car is at y=199, segment at y=200 → 1 unit left of centreline
        # (since +y = right, -y = left in y-down convention).
        assert left == pytest.approx(4.0, abs=1e-6)
        assert right == pytest.approx(6.0, abs=1e-6)

    def test_clamps_to_zero_when_off_track(self):
        # Car way off the right side of a 10-wide segment.
        track = _track([_seg(0, 0, 100, 0, width=10.0)])
        left, right = boundary_distances((50.0, 20.0), track)
        # signed_right_offset = 20 ⇒ right = 5 - 20 = -15 ⇒ clamp to 0.
        # left should reflect how deep off-track the car is.
        assert right == 0.0
        assert left > 5.0  # at least more than half-width

    def test_no_segments_returns_zero(self):
        track = _track([])
        left, right = boundary_distances((50.0, 0.0), track)
        assert left == 0.0
        assert right == 0.0

    def test_uses_segment_width_at_projection_point(self):
        # Segment that widens from 10 to 30 along its length.
        seg = TrackSegment(
            start=TrackPoint(x=0, y=0, width=10.0, surface=SurfaceType.ASPHALT),
            end=TrackPoint(x=100, y=0, width=30.0, surface=SurfaceType.ASPHALT),
        )
        track = _track([seg])
        # At t=0.5 width should be 20. Car on centreline → 10 each side.
        left, right = boundary_distances((50.0, 0.0), track)
        assert left == pytest.approx(10.0, abs=1e-6)
        assert right == pytest.approx(10.0, abs=1e-6)


# ===== Upcoming turn =====


class TestUpcomingTurn:
    def test_three_collinear_checkpoints_are_straight(self):
        track = _track(
            [_seg(0, 0, 300, 0)],
            checkpoints=[(100.0, 0.0), (200.0, 0.0), (300.0, 0.0)],
            start_position=(0.0, 0.0),
        )
        direction, sharpness = upcoming_turn(track, next_checkpoint_idx=1)
        assert direction == "straight"
        assert sharpness == pytest.approx(0.0, abs=1e-6)

    def test_right_turn_in_y_down(self):
        # Road goes east then turns south (visually right). next_cp = 1
        # means we're approaching the second checkpoint where the bend
        # happens.
        track = _track(
            [_seg(0, 0, 200, 0)],
            checkpoints=[(100.0, 0.0), (200.0, 0.0), (200.0, 100.0)],
        )
        direction, sharpness = upcoming_turn(track, next_checkpoint_idx=1)
        assert direction == "right"
        # 90° corner → sharpness ≈ 0.5 (since 1.0 = 180°)
        assert sharpness == pytest.approx(0.5, abs=1e-3)

    def test_left_turn_in_y_down(self):
        # Road east then north (-y, visually left).
        track = _track(
            [_seg(0, 0, 200, 0)],
            checkpoints=[(100.0, 0.0), (200.0, 0.0), (200.0, -100.0)],
        )
        direction, sharpness = upcoming_turn(track, next_checkpoint_idx=1)
        assert direction == "left"
        assert sharpness == pytest.approx(0.5, abs=1e-3)

    def test_hairpin_has_high_sharpness(self):
        # Road east, then back west — 180° turn.
        track = _track(
            [_seg(0, 0, 200, 0)],
            checkpoints=[(100.0, 0.0), (200.0, 0.0), (100.0, 0.0)],
        )
        _, sharpness = upcoming_turn(track, next_checkpoint_idx=1)
        # 180° = full sharpness
        assert sharpness == pytest.approx(1.0, abs=1e-3)

    def test_first_checkpoint_uses_start_position_as_previous(self):
        # next_checkpoint = 0: "previous" anchor is start_position.
        track = _track(
            [_seg(0, 0, 200, 0)],
            checkpoints=[(100.0, 0.0), (100.0, 100.0)],
            start_position=(0.0, 0.0),
        )
        # start→cp[0] = east. cp[0]→cp[1] = south. Right turn at cp[0].
        direction, sharpness = upcoming_turn(track, next_checkpoint_idx=0)
        assert direction == "right"
        assert sharpness > 0.4

    def test_last_checkpoint_with_no_next_returns_straight(self):
        track = _track(
            [_seg(0, 0, 200, 0)],
            checkpoints=[(100.0, 0.0), (200.0, 0.0)],
        )
        direction, sharpness = upcoming_turn(track, next_checkpoint_idx=1)
        assert direction == "straight"
        assert sharpness == 0.0

    def test_out_of_bounds_index_returns_straight(self):
        track = _track(
            [_seg(0, 0, 200, 0)],
            checkpoints=[(100.0, 0.0)],
        )
        for idx in (-1, 5, 100):
            d, s = upcoming_turn(track, next_checkpoint_idx=idx)
            assert d == "straight"
            assert s == 0.0


# ===== Upcoming surface =====


class TestUpcomingSurface:
    def test_returns_surface_of_segment_near_next_checkpoint(self):
        # Two segments with different surfaces; checkpoint near segment 2.
        track = _track(
            [
                _seg(0, 0, 100, 0, surface=SurfaceType.ASPHALT),
                _seg(100, 0, 200, 0, surface=SurfaceType.GRAVEL),
            ],
            checkpoints=[(150.0, 0.0)],
        )
        assert upcoming_surface(track, next_checkpoint_idx=0) == "gravel"

    def test_returns_asphalt_when_no_checkpoints(self):
        track = _track([_seg(0, 0, 100, 0, surface=SurfaceType.ICE)], checkpoints=[])
        assert upcoming_surface(track, next_checkpoint_idx=0) == "asphalt"

    def test_returns_asphalt_when_index_out_of_range(self):
        track = _track(
            [_seg(0, 0, 100, 0, surface=SurfaceType.ICE)],
            checkpoints=[(50.0, 0.0)],
        )
        assert upcoming_surface(track, next_checkpoint_idx=5) == "asphalt"
