"""
Track generation for CodeRally.

This module implements procedural track generation with smooth curves,
varied surfaces, and automatic checkpoint placement.
"""

import math
import random
from dataclasses import dataclass, field
from typing import List, Tuple, Optional
from enum import Enum

from app.config import get_settings


class SurfaceType(Enum):
    """Track surface types with different grip characteristics."""
    ASPHALT = "asphalt"
    WET = "wet"
    GRAVEL = "gravel"
    ICE = "ice"


@dataclass
class TrackPoint:
    """A point along the track centerline."""
    x: float
    y: float
    width: float
    surface: SurfaceType = SurfaceType.ASPHALT


@dataclass
class TrackSegment:
    """
    A segment of the track between two points.

    Attributes:
        start: Starting point of segment
        end: Ending point of segment
        control1: First bezier control point (optional)
        control2: Second bezier control point (optional)
    """
    start: TrackPoint
    end: TrackPoint
    control1: Optional[Tuple[float, float]] = None
    control2: Optional[Tuple[float, float]] = None

    def is_straight(self) -> bool:
        """Check if this segment is a straight line."""
        return self.control1 is None and self.control2 is None


@dataclass
class Checkpoint:
    """
    A checkpoint that cars must pass through.

    Attributes:
        position: Center position of checkpoint
        angle: Angle perpendicular to track (radians)
        width: Width of checkpoint
        index: Checkpoint number in sequence
    """
    position: Tuple[float, float]
    angle: float
    width: float
    index: int


@dataclass
class Track:
    """
    Complete track definition.

    Attributes:
        segments: List of track segments forming a closed loop
        checkpoints: Ordered list of checkpoints
        start_position: Starting position for cars
        start_heading: Starting heading for cars (radians)
        total_length: Approximate total track length
    """
    segments: List[TrackSegment]
    checkpoints: List[Checkpoint]
    start_position: Tuple[float, float]
    start_heading: float
    total_length: float = 0.0


class TrackGenerator:
    """
    Procedural track generator.

    Generates varied, driveable racing tracks with smooth curves,
    checkpoints, and different surface types.
    """

    def __init__(self, seed: Optional[int] = None):
        """
        Initialize track generator.

        Args:
            seed: Random seed for reproducible tracks (optional)
        """
        self.settings = get_settings()
        self.config = self.settings.game
        self.physics = self.settings.physics

        if seed is not None:
            random.seed(seed)

    def generate(self, difficulty: str = "medium") -> Track:
        """
        Generate a complete racing track.

        Args:
            difficulty: Track difficulty ("easy", "medium", "hard")

        Returns:
            Generated Track object
        """
        # Generate control points for track shape
        control_points = self._generate_control_points(difficulty)

        # Create smooth segments between control points
        segments = self._create_segments(control_points)

        # Calculate total track length
        total_length = self._calculate_track_length(segments)

        # Place checkpoints along the track
        checkpoints = self._place_checkpoints(segments, total_length)

        # Determine start position and heading
        start_pos, start_heading = self._get_start_position(segments)

        return Track(
            segments=segments,
            checkpoints=checkpoints,
            start_position=start_pos,
            start_heading=start_heading,
            total_length=total_length
        )

    def _generate_control_points(self, difficulty: str) -> List[TrackPoint]:
        """
        Generate control points that define the track shape.

        Args:
            difficulty: Track difficulty level

        Returns:
            List of control points forming a closed loop
        """
        # Number of control points based on difficulty
        num_points = {
            "easy": 6,
            "medium": 8,
            "hard": 12
        }.get(difficulty, 8)

        # Generate points in a roughly circular pattern with variation
        points = []
        base_radius = 500.0  # Base radius for the track

        for i in range(num_points):
            angle = (2 * math.pi * i) / num_points

            # Add randomness to radius and angle
            radius_variation = random.uniform(0.7, 1.3)
            angle_variation = random.uniform(-0.2, 0.2)

            radius = base_radius * radius_variation
            actual_angle = angle + angle_variation

            x = radius * math.cos(actual_angle)
            y = radius * math.sin(actual_angle)

            # Random track width
            width = random.uniform(
                self.config.TRACK_WIDTH * 0.8,
                self.config.TRACK_WIDTH * 1.2
            )

            # Random surface type (weighted toward asphalt)
            surface = self._choose_surface()

            points.append(TrackPoint(x, y, width, surface))

        return points

    def _choose_surface(self) -> SurfaceType:
        """
        Choose a random surface type with weighted probabilities.

        Returns:
            Selected SurfaceType
        """
        rand = random.random()

        weights = self.config
        asphalt = weights.SURFACE_ASPHALT_WEIGHT
        wet = weights.SURFACE_WET_WEIGHT
        gravel = weights.SURFACE_GRAVEL_WEIGHT
        ice = weights.SURFACE_ICE_WEIGHT

        total = asphalt + wet + gravel + ice
        asphalt /= total
        wet /= total
        gravel /= total

        if rand < asphalt:
            return SurfaceType.ASPHALT
        elif rand < asphalt + wet:
            return SurfaceType.WET
        elif rand < asphalt + wet + gravel:
            return SurfaceType.GRAVEL
        else:
            return SurfaceType.ICE

    def _create_segments(self, control_points: List[TrackPoint]) -> List[TrackSegment]:
        """
        Create smooth track segments between control points using bezier curves.

        Args:
            control_points: List of control points

        Returns:
            List of track segments forming a closed loop
        """
        segments = []
        num_points = len(control_points)

        for i in range(num_points):
            start_point = control_points[i]
            end_point = control_points[(i + 1) % num_points]

            # Calculate bezier control points for smooth curves
            # Use the adjacent points to determine curve direction
            prev_point = control_points[(i - 1) % num_points]
            next_next_point = control_points[(i + 2) % num_points]

            # Control point 1: offset from start toward end
            dx1 = end_point.x - prev_point.x
            dy1 = end_point.y - prev_point.y
            length1 = math.sqrt(dx1**2 + dy1**2)
            if length1 > 0:
                dx1 /= length1
                dy1 /= length1

            offset1 = 0.3 * math.sqrt((end_point.x - start_point.x)**2 + (end_point.y - start_point.y)**2)
            control1 = (
                start_point.x + dx1 * offset1,
                start_point.y + dy1 * offset1
            )

            # Control point 2: offset from end toward start
            dx2 = start_point.x - next_next_point.x
            dy2 = start_point.y - next_next_point.y
            length2 = math.sqrt(dx2**2 + dy2**2)
            if length2 > 0:
                dx2 /= length2
                dy2 /= length2

            offset2 = 0.3 * math.sqrt((end_point.x - start_point.x)**2 + (end_point.y - start_point.y)**2)
            control2 = (
                end_point.x + dx2 * offset2,
                end_point.y + dy2 * offset2
            )

            segments.append(TrackSegment(
                start=start_point,
                end=end_point,
                control1=control1,
                control2=control2
            ))

        return segments

    def _calculate_track_length(self, segments: List[TrackSegment]) -> float:
        """
        Calculate approximate total track length.

        Args:
            segments: List of track segments

        Returns:
            Approximate total length
        """
        total_length = 0.0

        for segment in segments:
            if segment.is_straight():
                # Straight line distance
                dx = segment.end.x - segment.start.x
                dy = segment.end.y - segment.start.y
                total_length += math.sqrt(dx**2 + dy**2)
            else:
                # Approximate bezier curve length with sampling
                num_samples = 20
                prev_x = segment.start.x
                prev_y = segment.start.y

                for i in range(1, num_samples + 1):
                    t = i / num_samples
                    x, y = self._bezier_point(
                        (segment.start.x, segment.start.y),
                        segment.control1,
                        segment.control2,
                        (segment.end.x, segment.end.y),
                        t
                    )

                    dx = x - prev_x
                    dy = y - prev_y
                    total_length += math.sqrt(dx**2 + dy**2)

                    prev_x = x
                    prev_y = y

        return total_length

    def _bezier_point(
        self,
        p0: Tuple[float, float],
        p1: Tuple[float, float],
        p2: Tuple[float, float],
        p3: Tuple[float, float],
        t: float
    ) -> Tuple[float, float]:
        """
        Calculate point on cubic bezier curve.

        Args:
            p0: Start point
            p1: First control point
            p2: Second control point
            p3: End point
            t: Parameter (0 to 1)

        Returns:
            Point on curve at parameter t
        """
        # Cubic bezier formula
        mt = 1 - t
        mt2 = mt * mt
        mt3 = mt2 * mt
        t2 = t * t
        t3 = t2 * t

        x = mt3 * p0[0] + 3 * mt2 * t * p1[0] + 3 * mt * t2 * p2[0] + t3 * p3[0]
        y = mt3 * p0[1] + 3 * mt2 * t * p1[1] + 3 * mt * t2 * p2[1] + t3 * p3[1]

        return (x, y)

    def _place_checkpoints(self, segments: List[TrackSegment], total_length: float) -> List[Checkpoint]:
        """
        Place checkpoints evenly along the track.

        Args:
            segments: List of track segments
            total_length: Total track length

        Returns:
            List of checkpoints
        """
        # Place one checkpoint per segment for simplicity
        checkpoints = []

        for i, segment in enumerate(segments):
            # Place checkpoint at midpoint of segment
            t = 0.5

            if segment.is_straight():
                x = segment.start.x + t * (segment.end.x - segment.start.x)
                y = segment.start.y + t * (segment.end.y - segment.start.y)

                # Calculate angle perpendicular to segment
                dx = segment.end.x - segment.start.x
                dy = segment.end.y - segment.start.y
                angle = math.atan2(dy, dx)
            else:
                # Get point on bezier curve
                x, y = self._bezier_point(
                    (segment.start.x, segment.start.y),
                    segment.control1,
                    segment.control2,
                    (segment.end.x, segment.end.y),
                    t
                )

                # Calculate tangent to curve for angle
                # Sample two nearby points to estimate tangent
                x1, y1 = self._bezier_point(
                    (segment.start.x, segment.start.y),
                    segment.control1,
                    segment.control2,
                    (segment.end.x, segment.end.y),
                    t - 0.01
                )
                x2, y2 = self._bezier_point(
                    (segment.start.x, segment.start.y),
                    segment.control1,
                    segment.control2,
                    (segment.end.x, segment.end.y),
                    t + 0.01
                )

                dx = x2 - x1
                dy = y2 - y1
                angle = math.atan2(dy, dx)

            checkpoints.append(Checkpoint(
                position=(x, y),
                angle=angle,
                width=segment.start.width,
                index=i
            ))

        return checkpoints

    def _get_start_position(self, segments: List[TrackSegment]) -> Tuple[Tuple[float, float], float]:
        """
        Get starting position and heading for cars.

        Args:
            segments: List of track segments

        Returns:
            Tuple of (position, heading)
        """
        # Start at the beginning of the first segment
        start_segment = segments[0]
        position = (start_segment.start.x, start_segment.start.y)

        # Heading toward the first control point or end point
        if start_segment.control1:
            dx = start_segment.control1[0] - start_segment.start.x
            dy = start_segment.control1[1] - start_segment.start.y
        else:
            dx = start_segment.end.x - start_segment.start.x
            dy = start_segment.end.y - start_segment.start.y

        heading = math.atan2(dy, dx)

        return position, heading
