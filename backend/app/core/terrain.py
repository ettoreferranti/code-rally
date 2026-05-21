"""Real-geometry helpers for LLM/bot observations.

These functions replace the long-standing hardcoded placeholders in
``bot_manager.py`` (``distance_to_boundary_left/right=100.0``,
``upcoming_surface="asphalt"``, ``upcoming_turn="straight"``,
``turn_sharpness=0.0``) so the LLM strategist actually sees the track
ahead.

Conventions
-----------
- **y-DOWN** (#164). The engine, controller, observation, and these
  helpers all use the convention that ``+y`` is "down on screen" and
  ``+y`` from a ``+x``-facing driver is "to the driver's right". A
  road that bends visually right from the driver's perspective
  produces ``upcoming_turn == "right"``, and a car off the right side
  of the track has ``signed_lateral_right > 0``.
- All distances are in engine units (≈ metres for HUD purposes).
- ``turn_sharpness`` is the absolute exterior angle at a checkpoint
  divided by π — so 90° → 0.5, a 180° hairpin → 1.0, straight → 0.0.

The functions are pure: they take a position or index plus a ``Track``
and return primitives. They never raise on missing data — out-of-range
indices yield "straight"/0.0 and an empty-segments track yields zero
boundary distances. Callers (the bot manager) should never need
``try/except`` around these.
"""

from __future__ import annotations

import math
from typing import Tuple

from app.core.track import SurfaceType, Track, TrackSegment


_STRAIGHT_THRESHOLD_DEG = 5.0  # below this, treat the corner as straight


def boundary_distances(
    position: Tuple[float, float],
    track: Track,
) -> Tuple[float, float]:
    """Return ``(left_m, right_m)`` for the given car position.

    Both numbers are non-negative. "Left" / "right" are relative to the
    direction of the nearest track segment (in y-DOWN), so they
    correspond to the driver's left/right when the car is moving
    forward along the segment. When the car is off-track, the
    appropriate side is clamped to 0.0 and the opposite side reflects
    how far past the centreline the car is.
    """
    if not track.segments:
        return 0.0, 0.0

    closest_seg: TrackSegment | None = None
    closest_dist = math.inf
    closest_t = 0.0
    for seg in track.segments:
        t, perp = _project_point_onto_segment(position, seg)
        if perp < closest_dist:
            closest_dist = perp
            closest_seg = seg
            closest_t = t
    assert closest_seg is not None  # segments non-empty above

    direction_unit = _segment_direction_unit(closest_seg)
    signed_right = _signed_lateral_right(position, closest_seg, direction_unit)

    width = _lerp(closest_seg.start.width, closest_seg.end.width, closest_t)
    half = width / 2.0
    left = half + signed_right
    right = half - signed_right
    return max(0.0, left), max(0.0, right)


def upcoming_turn(
    track: Track,
    next_checkpoint_idx: int,
) -> Tuple[str, float]:
    """Direction and sharpness of the turn AT ``checkpoints[next_idx]``.

    Returns ``("left"|"right"|"straight", sharpness)`` where sharpness
    is in [0.0, 1.0]. When the checkpoint that defines the bend's
    "previous" or "next" anchor is missing, returns
    ``("straight", 0.0)``. For ``next_checkpoint_idx == 0`` the
    previous anchor is the track's ``start_position`` (since the car
    drove from there to checkpoint 0).
    """
    checkpoints = track.checkpoints
    n = len(checkpoints)
    if next_checkpoint_idx < 0 or next_checkpoint_idx >= n:
        return "straight", 0.0

    # Need a "next-next" anchor to define a bend AT next_checkpoint.
    if next_checkpoint_idx + 1 >= n:
        return "straight", 0.0

    if next_checkpoint_idx == 0:
        prev = track.start_position
    else:
        prev = checkpoints[next_checkpoint_idx - 1].position

    here = checkpoints[next_checkpoint_idx].position
    nxt = checkpoints[next_checkpoint_idx + 1].position

    vin = (here[0] - prev[0], here[1] - prev[1])
    vout = (nxt[0] - here[0], nxt[1] - here[1])

    if _is_zero(vin) or _is_zero(vout):
        return "straight", 0.0

    cross = vin[0] * vout[1] - vin[1] * vout[0]
    dot = vin[0] * vout[0] + vin[1] * vout[1]
    angle_rad = math.atan2(cross, dot)
    angle_deg = math.degrees(angle_rad)

    if abs(angle_deg) < _STRAIGHT_THRESHOLD_DEG:
        return "straight", 0.0

    # y-DOWN convention: positive cross ⇒ vout rotated CW visually from
    # vin ⇒ the road bends to the visual right.
    direction = "right" if angle_rad > 0 else "left"
    sharpness = min(1.0, abs(angle_rad) / math.pi)
    return direction, sharpness


def upcoming_surface(track: Track, next_checkpoint_idx: int) -> str:
    """Surface type of the segment closest to ``checkpoints[next_idx]``.

    Falls back to ``"asphalt"`` when the index is out of range or no
    checkpoints exist. Returns a lowercase string ("asphalt", "gravel",
    "ice", "wet", ...) matching the engine's surface enum values.
    """
    checkpoints = track.checkpoints
    if not checkpoints or next_checkpoint_idx < 0 or next_checkpoint_idx >= len(
        checkpoints
    ):
        return "asphalt"

    target = checkpoints[next_checkpoint_idx].position

    if not track.segments:
        return "asphalt"

    closest_seg: TrackSegment | None = None
    closest_dist = math.inf
    for seg in track.segments:
        _, perp = _project_point_onto_segment(target, seg)
        if perp < closest_dist:
            closest_dist = perp
            closest_seg = seg
    assert closest_seg is not None

    surface = closest_seg.start.surface
    if isinstance(surface, SurfaceType):
        return surface.value.lower()
    return str(surface).lower()


# ===== Internals =====


def _project_point_onto_segment(
    point: Tuple[float, float],
    segment: TrackSegment,
) -> Tuple[float, float]:
    """Return ``(t_clamped, perpendicular_distance)``.

    ``t_clamped`` is the parameter along ``start → end`` clamped to
    [0, 1]. The distance is from ``point`` to the closest point on the
    segment.
    """
    ax, ay = segment.start.x, segment.start.y
    bx, by = segment.end.x, segment.end.y
    abx, aby = bx - ax, by - ay
    ab_len2 = abx * abx + aby * aby
    if ab_len2 == 0:
        return 0.0, math.hypot(point[0] - ax, point[1] - ay)
    apx, apy = point[0] - ax, point[1] - ay
    t = (apx * abx + apy * aby) / ab_len2
    t_clamped = max(0.0, min(1.0, t))
    closest_x = ax + t_clamped * abx
    closest_y = ay + t_clamped * aby
    return t_clamped, math.hypot(point[0] - closest_x, point[1] - closest_y)


def _segment_direction_unit(segment: TrackSegment) -> Tuple[float, float]:
    dx = segment.end.x - segment.start.x
    dy = segment.end.y - segment.start.y
    norm = math.hypot(dx, dy)
    if norm == 0.0:
        return 1.0, 0.0  # degenerate; pick an arbitrary direction
    return dx / norm, dy / norm


def _signed_lateral_right(
    point: Tuple[float, float],
    segment: TrackSegment,
    direction_unit: Tuple[float, float],
) -> float:
    """Signed perpendicular offset of ``point`` from the segment line.

    Positive ⇒ point is to the visual right of the segment direction
    (y-DOWN). Same sign convention as the controller's ``(-uy, ux)``
    perpendicular for racing-line offsets.
    """
    dx, dy = direction_unit
    apx = point[0] - segment.start.x
    apy = point[1] - segment.start.y
    # right_perp = (-dy, dx); dot with (apx, apy).
    return apx * (-dy) + apy * dx


def _is_zero(v: Tuple[float, float]) -> bool:
    return v[0] == 0.0 and v[1] == 0.0


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t
