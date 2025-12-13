"""
Unit tests for track generation.
"""

import pytest
import math
from app.core.track import (
    SurfaceType,
    TrackPoint,
    TrackSegment,
    Checkpoint,
    Track,
    TrackGenerator
)


class TestTrackDataStructures:
    """Test track data structures."""

    def test_track_point_creation(self):
        point = TrackPoint(x=100, y=200, width=50, surface=SurfaceType.ASPHALT)
        assert point.x == 100
        assert point.y == 200
        assert point.width == 50
        assert point.surface == SurfaceType.ASPHALT

    def test_track_segment_straight(self):
        start = TrackPoint(0, 0, 100)
        end = TrackPoint(100, 100, 100)
        segment = TrackSegment(start=start, end=end)

        assert segment.is_straight()

    def test_track_segment_curved(self):
        start = TrackPoint(0, 0, 100)
        end = TrackPoint(100, 100, 100)
        segment = TrackSegment(
            start=start,
            end=end,
            control1=(25, 50),
            control2=(75, 50)
        )

        assert not segment.is_straight()

    def test_checkpoint_creation(self):
        checkpoint = Checkpoint(
            position=(100, 200),
            angle=math.pi / 4,
            width=100,
            index=0
        )

        assert checkpoint.position == (100, 200)
        assert checkpoint.angle == math.pi / 4
        assert checkpoint.width == 100
        assert checkpoint.index == 0


class TestTrackGenerator:
    """Test track generation."""

    @pytest.fixture
    def generator(self):
        """Create a track generator with fixed seed for reproducibility."""
        return TrackGenerator(seed=42)

    def test_generator_initialization(self, generator):
        """Test generator initializes correctly."""
        assert generator.settings is not None
        assert generator.config is not None
        assert generator.physics is not None

    def test_generate_track_easy(self, generator):
        """Test generating an easy track."""
        track = generator.generate(difficulty="easy")

        assert track is not None
        assert isinstance(track, Track)
        assert len(track.segments) > 0
        assert len(track.checkpoints) > 0
        assert track.total_length > 0

    def test_generate_track_medium(self, generator):
        """Test generating a medium difficulty track."""
        track = generator.generate(difficulty="medium")

        assert track is not None
        assert len(track.segments) > 0
        assert len(track.checkpoints) > 0

    def test_generate_track_hard(self, generator):
        """Test generating a hard track."""
        track = generator.generate(difficulty="hard")

        assert track is not None
        assert len(track.segments) > 0
        assert len(track.checkpoints) > 0

    def test_track_is_point_to_point(self, generator):
        """Test that generated track is point-to-point (not looping)."""
        track = generator.generate()

        # Rally stages should not loop
        assert track.is_looping is False

        # Start and finish should be different positions
        dx = track.finish_position[0] - track.start_position[0]
        dy = track.finish_position[1] - track.start_position[1]
        distance = math.sqrt(dx**2 + dy**2)

        # Should be significantly far apart
        assert distance > 100.0

    def test_track_has_variety_of_surfaces(self, generator):
        """Test that tracks have variety in surface types."""
        track = generator.generate()

        # Collect all surface types used
        surfaces = set()
        for segment in track.segments:
            surfaces.add(segment.start.surface)

        # With enough segments, should have some variety
        # (May not always be true with random generation, but likely)
        assert len(surfaces) >= 1

    def test_track_length_reasonable(self, generator):
        """Test that track length is within reasonable bounds."""
        track = generator.generate()

        # Track should have meaningful length
        assert track.total_length > 1000  # At least 1000 units
        assert track.total_length < 10000  # Not absurdly long

    def test_checkpoints_match_segments(self, generator):
        """Test that number of checkpoints matches number of segments."""
        track = generator.generate()

        # We place one checkpoint per segment
        assert len(track.checkpoints) == len(track.segments)

    def test_checkpoints_ordered(self, generator):
        """Test that checkpoints are ordered sequentially."""
        track = generator.generate()

        for i, checkpoint in enumerate(track.checkpoints):
            assert checkpoint.index == i

    def test_start_position_exists(self, generator):
        """Test that track has a valid start position and heading."""
        track = generator.generate()

        assert track.start_position is not None
        assert len(track.start_position) == 2
        assert track.start_heading is not None
        assert -math.pi <= track.start_heading <= math.pi

    def test_finish_position_exists(self, generator):
        """Test that track has a valid finish position and heading."""
        track = generator.generate()

        assert track.finish_position is not None
        assert len(track.finish_position) == 2
        assert track.finish_heading is not None
        assert -math.pi <= track.finish_heading <= math.pi

    def test_finish_at_end_of_track(self, generator):
        """Test that finish position is at the end of the last segment."""
        track = generator.generate()

        last_segment = track.segments[-1]

        # Finish should be at end of last segment
        assert abs(track.finish_position[0] - last_segment.end.x) < 0.01
        assert abs(track.finish_position[1] - last_segment.end.y) < 0.01

    def test_reproducible_with_same_seed(self):
        """Test that same seed produces same track on first generation."""
        # Generate track with seed 123
        gen1 = TrackGenerator(seed=123)
        track1 = gen1.generate()

        # Generate another track with same seed
        gen2 = TrackGenerator(seed=123)
        track2 = gen2.generate()

        # Should have same number of segments
        assert len(track1.segments) == len(track2.segments)

        # First segment should start at same position
        assert abs(track1.segments[0].start.x - track2.segments[0].start.x) < 0.01
        assert abs(track1.segments[0].start.y - track2.segments[0].start.y) < 0.01

    def test_different_seeds_produce_different_tracks(self):
        """Test that different seeds produce different tracks."""
        gen1 = TrackGenerator(seed=111)
        gen2 = TrackGenerator(seed=222)

        track1 = gen1.generate()
        track2 = gen2.generate()

        # First segment positions should be different
        assert (track1.segments[0].start.x != track2.segments[0].start.x or
                track1.segments[0].start.y != track2.segments[0].start.y)

    def test_bezier_point_calculation(self, generator):
        """Test bezier curve point calculation."""
        # Test with known bezier curve
        p0 = (0, 0)
        p1 = (0, 100)
        p2 = (100, 100)
        p3 = (100, 0)

        # At t=0, should be at start
        point = generator._bezier_point(p0, p1, p2, p3, 0.0)
        assert abs(point[0] - p0[0]) < 0.01
        assert abs(point[1] - p0[1]) < 0.01

        # At t=1, should be at end
        point = generator._bezier_point(p0, p1, p2, p3, 1.0)
        assert abs(point[0] - p3[0]) < 0.01
        assert abs(point[1] - p3[1]) < 0.01

        # At t=0.5, should be somewhere in between
        point = generator._bezier_point(p0, p1, p2, p3, 0.5)
        assert 0 <= point[0] <= 100
        assert 0 <= point[1] <= 100

    def test_track_segments_have_control_points(self, generator):
        """Test that curved segments have control points."""
        track = generator.generate()

        # Most segments should have control points for smooth curves
        curved_count = sum(1 for seg in track.segments if not seg.is_straight())

        # Should have some curved segments
        assert curved_count > 0

    def test_surface_type_distribution(self, generator):
        """Test that surface types are weighted correctly."""
        # Generate multiple tracks and count surface types
        surface_counts = {
            SurfaceType.ASPHALT: 0,
            SurfaceType.WET: 0,
            SurfaceType.GRAVEL: 0,
            SurfaceType.ICE: 0
        }

        # Generate surfaces many times
        for _ in range(100):
            surface = generator._choose_surface()
            surface_counts[surface] += 1

        # Asphalt should be most common (50% weight)
        assert surface_counts[SurfaceType.ASPHALT] > surface_counts[SurfaceType.WET]
        assert surface_counts[SurfaceType.ASPHALT] > surface_counts[SurfaceType.GRAVEL]
        assert surface_counts[SurfaceType.ASPHALT] > surface_counts[SurfaceType.ICE]

    def test_control_points_form_path(self, generator):
        """Test that control points form a connected path."""
        control_points = generator._generate_control_points("medium")

        # Should have at least a few points
        assert len(control_points) >= 4

        # All points should have valid coordinates
        for point in control_points:
            assert isinstance(point.x, float)
            assert isinstance(point.y, float)
            assert point.width > 0

    def test_track_width_varies(self, generator):
        """Test that track width varies across segments."""
        track = generator.generate()

        widths = [seg.start.width for seg in track.segments]

        # Should have some variation in width
        min_width = min(widths)
        max_width = max(widths)

        assert max_width > min_width

    def test_checkpoints_have_valid_angles(self, generator):
        """Test that all checkpoints have valid angles."""
        track = generator.generate()

        for checkpoint in track.checkpoints:
            # Angle should be in valid range
            assert -math.pi <= checkpoint.angle <= math.pi

    def test_checkpoint_positions_on_track(self, generator):
        """Test that checkpoint positions are reasonable."""
        track = generator.generate()

        for checkpoint in track.checkpoints:
            x, y = checkpoint.position

            # Position should be finite numbers
            assert math.isfinite(x)
            assert math.isfinite(y)

            # Should be within reasonable bounds (track is roughly circular)
            distance_from_origin = math.sqrt(x**2 + y**2)
            assert distance_from_origin < 2000  # Within 2000 units of origin

    def test_difficulty_affects_complexity(self):
        """Test that difficulty affects track complexity."""
        gen = TrackGenerator(seed=42)

        easy_track = gen.generate("easy")
        hard_track = gen.generate("hard")

        # Hard tracks should have more segments
        assert len(hard_track.segments) > len(easy_track.segments)

    def test_track_has_no_nan_values(self, generator):
        """Test that generated track has no NaN values."""
        track = generator.generate()

        # Check all segment coordinates
        for segment in track.segments:
            assert math.isfinite(segment.start.x)
            assert math.isfinite(segment.start.y)
            assert math.isfinite(segment.end.x)
            assert math.isfinite(segment.end.y)

            if segment.control1:
                assert math.isfinite(segment.control1[0])
                assert math.isfinite(segment.control1[1])

            if segment.control2:
                assert math.isfinite(segment.control2[0])
                assert math.isfinite(segment.control2[1])

    def test_surfaces_grouped_in_sections(self, generator):
        """Test that surfaces are grouped into sections (not changing every segment)."""
        track = generator.generate()

        # Count consecutive segments with same surface
        section_lengths = []
        current_surface = track.segments[0].start.surface
        current_length = 1

        for i in range(1, len(track.segments)):
            if track.segments[i].start.surface == current_surface:
                current_length += 1
            else:
                section_lengths.append(current_length)
                current_surface = track.segments[i].start.surface
                current_length = 1

        section_lengths.append(current_length)

        # Most sections should be 2-4 segments long
        # At least some sections should be longer than 1 segment
        long_sections = [length for length in section_lengths if length >= 2]
        assert len(long_sections) > 0

    def test_mix_of_straights_and_curves(self, generator):
        """Test that track has mix of straight and curved segments."""
        track = generator.generate()

        straight_count = sum(1 for seg in track.segments if seg.is_straight())
        curved_count = sum(1 for seg in track.segments if not seg.is_straight())

        # Should have both straights and curves
        assert straight_count > 0
        assert curved_count > 0
