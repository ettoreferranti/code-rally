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
        segments: List of track segments (point-to-point for rally stages)
        checkpoints: Ordered list of checkpoints
        start_position: Starting position for cars
        start_heading: Starting heading for cars (radians)
        finish_position: Finish line position
        finish_heading: Finish line heading (radians)
        total_length: Approximate total track length
        is_looping: Whether track loops back to start (False for rally stages)
    """
    segments: List[TrackSegment]
    checkpoints: List[Checkpoint]
    start_position: Tuple[float, float]
    start_heading: float
    finish_position: Tuple[float, float]
    finish_heading: float
    total_length: float = 0.0
    is_looping: bool = False


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
        Generate a complete point-to-point rally stage.

        Args:
            difficulty: Track difficulty ("easy", "medium", "hard")

        Returns:
            Generated Track object
        """
        # Generate control points for track shape
        control_points = self._generate_control_points(difficulty)

        # Create smooth segments between control points
        segments, curve_intensities = self._create_segments(control_points, difficulty)

        # Calculate total track length
        total_length = self._calculate_track_length(segments)

        # Place checkpoints along the track
        checkpoints = self._place_checkpoints(segments, total_length)

        # Determine start position and heading
        start_pos, start_heading = self._get_start_position(segments)

        # Determine finish position and heading
        finish_pos, finish_heading = self._get_finish_position(segments)

        return Track(
            segments=segments,
            checkpoints=checkpoints,
            start_position=start_pos,
            start_heading=start_heading,
            finish_position=finish_pos,
            finish_heading=finish_heading,
            total_length=total_length,
            is_looping=False
        )

    def _generate_control_points(self, difficulty: str) -> List[TrackPoint]:
        """
        Generate control points for a point-to-point rally stage.

        Args:
            difficulty: Track difficulty level

        Returns:
            List of control points forming a winding path from start to finish
        """
        # Number of control points based on difficulty
        num_points = {
            "easy": 8,
            "medium": 13,  # Match frontend: 13 points = 12 segments
            "hard": 18
        }.get(difficulty, 13)

        # Generate points in a winding path from top-left to bottom-right
        points = []

        # Define start and end positions
        start_x = -600.0
        start_y = -500.0
        end_x = -400.0
        end_y = 700.0

        # Calculate spacing
        total_distance_x = end_x - start_x
        total_distance_y = end_y - start_y

        for i in range(num_points):
            # Progress along the stage (0 to 1)
            progress = i / (num_points - 1)

            # Base position along the path
            base_x = start_x + progress * total_distance_x
            base_y = start_y + progress * total_distance_y

            # Add serpentine variation (side-to-side movement)
            # Stronger variation in the middle, less at start/end
            variation_strength = math.sin(progress * math.pi) * 300.0
            serpentine_offset = math.sin(progress * math.pi * 3) * variation_strength

            x = base_x + serpentine_offset
            y = base_y + random.uniform(-50, 50)  # Small random variation

            # Track width (slightly varied)
            width = self.config.STAGE_WIDTH * random.uniform(0.9, 1.1)

            # Surface will be assigned in sections later
            surface = SurfaceType.ASPHALT  # Placeholder

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

    def _create_segments(self, control_points: List[TrackPoint], difficulty: str) -> Tuple[List[TrackSegment], List[float]]:
        """
        Create track segments with varied curve intensities and surface sections.

        Args:
            control_points: List of control points
            difficulty: Track difficulty level

        Returns:
            Tuple of (segments list, curve intensities list)
        """
        segments = []
        num_points = len(control_points)
        num_segments = num_points - 1  # Point-to-point: no loop back

        # Generate curve intensities (0 = straight, higher = more curved)
        curve_intensities = self._generate_curve_intensities(num_segments, difficulty)

        # Assign surfaces in sections
        surfaces = self._assign_surface_sections(num_segments)

        for i in range(num_segments):
            start_point = control_points[i]
            end_point = control_points[i + 1]

            # Update surface from section assignment
            start_point = TrackPoint(
                x=start_point.x,
                y=start_point.y,
                width=start_point.width,
                surface=surfaces[i]
            )

            dx = end_point.x - start_point.x
            dy = end_point.y - start_point.y

            control1 = None
            control2 = None

            # Only add bezier curves if intensity > 0
            if curve_intensities[i] > 0:
                # Perpendicular offset for curve
                offset_x = -dy * curve_intensities[i]
                offset_y = dx * curve_intensities[i]

                control1_x = start_point.x + dx * 0.33 + offset_x
                control1_y = start_point.y + dy * 0.33 + offset_y
                control2_x = start_point.x + dx * 0.66 + offset_x
                control2_y = start_point.y + dy * 0.66 + offset_y

                control1 = (control1_x, control1_y)
                control2 = (control2_x, control2_y)

            segments.append(TrackSegment(
                start=start_point,
                end=end_point,
                control1=control1,
                control2=control2
            ))

        return segments, curve_intensities

    def _generate_curve_intensities(self, num_segments: int, difficulty: str) -> List[float]:
        """
        Generate curve intensity values for each segment.

        Args:
            num_segments: Number of segments
            difficulty: Track difficulty

        Returns:
            List of curve intensities (0 = straight, higher = sharper curve)
        """
        intensities = []

        # Difficulty affects curve sharpness
        max_intensity = {
            "easy": 0.3,
            "medium": 0.5,
            "hard": 0.7
        }.get(difficulty, 0.5)

        for i in range(num_segments):
            # Mix of straights and curves
            if random.random() < 0.3:  # 30% chance of straight
                intensities.append(0.0)
            elif random.random() < 0.5:  # Gentle curve
                intensities.append(random.uniform(0.1, max_intensity * 0.4))
            elif random.random() < 0.8:  # Medium curve
                intensities.append(random.uniform(max_intensity * 0.4, max_intensity * 0.7))
            else:  # Sharp hairpin
                intensities.append(random.uniform(max_intensity * 0.7, max_intensity))

        return intensities

    def _assign_surface_sections(self, num_segments: int) -> List[SurfaceType]:
        """
        Assign surfaces in sections for more realistic rally stages.

        Args:
            num_segments: Number of segments

        Returns:
            List of surface types, one per segment
        """
        surfaces = []

        # Define sections (each section is 2-4 segments long)
        i = 0
        while i < num_segments:
            # Choose surface type for this section
            surface = self._choose_surface()

            # Section length (2-4 segments, or however many remain)
            remaining = num_segments - i
            if remaining == 1:
                section_length = 1
            else:
                section_length = random.randint(2, min(4, remaining))

            # Assign this surface to all segments in the section
            for _ in range(section_length):
                if i < num_segments:
                    surfaces.append(surface)
                    i += 1

        return surfaces

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

    def _get_finish_position(self, segments: List[TrackSegment]) -> Tuple[Tuple[float, float], float]:
        """
        Get finish line position and heading for rally stage.

        Args:
            segments: List of track segments

        Returns:
            Tuple of (position, heading)
        """
        # Finish at the end of the last segment
        finish_segment = segments[-1]
        position = (finish_segment.end.x, finish_segment.end.y)

        # Heading from second-to-last point toward finish
        if finish_segment.control2:
            dx = finish_segment.end.x - finish_segment.control2[0]
            dy = finish_segment.end.y - finish_segment.control2[1]
        else:
            dx = finish_segment.end.x - finish_segment.start.x
            dy = finish_segment.end.y - finish_segment.start.y

        heading = math.atan2(dy, dx)

        return position, heading
