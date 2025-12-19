"""
Tests for raycast system.

Verifies that raycasts correctly detect:
- Track boundaries
- Other cars
- Obstacles
- Correct distances and hit types
"""

import math
import pytest

from app.core.raycast import RaycastSystem, RaycastResult
from app.core.physics import CarState, Vector2, create_car_at_position
from app.core.track import Track, ContainmentBoundary, Obstacle, TrackSegment, TrackPoint, Checkpoint, SurfaceType


class TestRaycastBasics:
    """Test basic raycast functionality."""

    def test_raycast_system_initialization(self):
        """Test creating a raycast system."""
        raycast = RaycastSystem(max_range=200.0)
        assert raycast.max_range == 200.0
        assert len(raycast.RAY_ANGLES) == 7

    def test_ray_angles_correct(self):
        """Test that ray angles are configured correctly."""
        raycast = RaycastSystem()

        # Expected angles (in radians)
        expected = [
            0.0,                  # forward
            -math.pi / 6,         # 30° right
            -math.pi / 3,         # 60° right
            -math.pi / 2,         # 90° right
            math.pi / 3,          # 60° left
            math.pi / 6,          # 30° left
            math.pi / 2,          # 90° left
        ]

        assert raycast.RAY_ANGLES == expected


class TestBoundaryDetection:
    """Test raycast detection of track boundaries."""

    def test_raycast_hits_boundary_ahead(self):
        """Test ray hitting a boundary wall directly ahead."""
        raycast = RaycastSystem(max_range=200.0)

        # Car at origin facing right
        car = create_car_at_position(0, 0, heading=0)

        # Simple boundary: vertical wall at x=50
        containment = ContainmentBoundary(
            left_points=[(50, -100), (50, 100)],
            right_points=[]
        )

        result = raycast._raycast_boundary(
            origin=car.position,
            direction=Vector2(1, 0),  # Facing right
            containment=containment
        )

        assert result is not None
        assert result.hit_type == "boundary"
        assert abs(result.distance - 50.0) < 0.1
        assert result.hit_position is not None

    def test_raycast_misses_boundary_behind(self):
        """Test ray missing a boundary that's behind the car."""
        raycast = RaycastSystem(max_range=200.0)

        car = create_car_at_position(0, 0, heading=0)

        # Boundary wall behind the car
        containment = ContainmentBoundary(
            left_points=[(-50, -100), (-50, 100)],
            right_points=[]
        )

        result = raycast._raycast_boundary(
            origin=car.position,
            direction=Vector2(1, 0),  # Facing right (away from wall)
            containment=containment
        )

        assert result is None

    def test_raycast_hits_angled_boundary(self):
        """Test ray hitting a diagonal boundary."""
        raycast = RaycastSystem(max_range=200.0)

        car = create_car_at_position(0, 0, heading=0)

        # Diagonal wall from (50, -50) to (50, 50)
        containment = ContainmentBoundary(
            left_points=[(50, -50), (50, 50)],
            right_points=[]
        )

        result = raycast._raycast_boundary(
            origin=car.position,
            direction=Vector2(1, 0),  # Facing right
            containment=containment
        )

        assert result is not None
        assert result.hit_type == "boundary"
        assert abs(result.distance - 50.0) < 0.1


class TestObstacleDetection:
    """Test raycast detection of obstacles."""

    def test_raycast_hits_obstacle(self):
        """Test ray hitting an obstacle."""
        raycast = RaycastSystem(max_range=200.0)

        car = create_car_at_position(0, 0, heading=0)

        # Obstacle directly ahead at x=50
        obstacle = Obstacle(
            position=(50, 0),
            radius=10,
            type="rock"
        )

        result = raycast._raycast_obstacle(
            origin=car.position,
            direction=Vector2(1, 0),  # Facing right
            obstacle=obstacle
        )

        assert result is not None
        assert result.hit_type == "obstacle"
        # Should hit at x=40 (50 - radius of 10)
        assert abs(result.distance - 40.0) < 0.1

    def test_raycast_misses_obstacle_to_side(self):
        """Test ray missing an obstacle that's off to the side."""
        raycast = RaycastSystem(max_range=200.0)

        car = create_car_at_position(0, 0, heading=0)

        # Obstacle to the side
        obstacle = Obstacle(
            position=(50, 50),  # Too far up
            radius=5,
            type="rock"
        )

        result = raycast._raycast_obstacle(
            origin=car.position,
            direction=Vector2(1, 0),  # Facing right
            obstacle=obstacle
        )

        assert result is None

    def test_raycast_hits_obstacle_edge(self):
        """Test ray grazing the edge of an obstacle."""
        raycast = RaycastSystem(max_range=200.0)

        car = create_car_at_position(0, 0, heading=0)

        # Obstacle with edge just touching ray path
        obstacle = Obstacle(
            position=(50, 10),  # Offset by exactly the radius
            radius=10,
            type="tree"
        )

        result = raycast._raycast_obstacle(
            origin=car.position,
            direction=Vector2(1, 0),  # Facing right
            obstacle=obstacle
        )

        assert result is not None
        assert result.hit_type == "obstacle"


class TestCarDetection:
    """Test raycast detection of other cars."""

    def test_raycast_hits_car_ahead(self):
        """Test ray hitting another car directly ahead."""
        raycast = RaycastSystem(max_range=200.0)

        car1 = create_car_at_position(0, 0, heading=0)
        car2 = create_car_at_position(50, 0, heading=0)

        result = raycast._raycast_car(
            origin=car1.position,
            direction=Vector2(1, 0),
            car=car2
        )

        assert result is not None
        assert result.hit_type == "car"
        # Should hit at approximately x=40 (50 - car_radius of 10)
        assert abs(result.distance - 40.0) < 0.1

    def test_raycast_misses_car_behind(self):
        """Test ray missing a car that's behind."""
        raycast = RaycastSystem(max_range=200.0)

        car1 = create_car_at_position(0, 0, heading=0)
        car2 = create_car_at_position(-50, 0, heading=0)

        result = raycast._raycast_car(
            origin=car1.position,
            direction=Vector2(1, 0),  # Facing right (away from car2)
            car=car2
        )

        assert result is None

    def test_raycast_misses_car_perpendicular(self):
        """Test ray missing a car that's perpendicular to ray path."""
        raycast = RaycastSystem(max_range=200.0)

        car1 = create_car_at_position(0, 0, heading=0)
        car2 = create_car_at_position(0, 50, heading=0)  # Directly above

        result = raycast._raycast_car(
            origin=car1.position,
            direction=Vector2(1, 0),  # Facing right
            car=car2
        )

        assert result is None


class TestCastAllRays:
    """Test casting all 7 rays from a car."""

    def test_cast_all_rays_returns_seven_results(self):
        """Test that cast_all_rays returns exactly 7 results."""
        raycast = RaycastSystem(max_range=200.0)

        car = create_car_at_position(0, 0, heading=0)

        # Minimal track with boundaries
        track = Track(
            segments=[],
            checkpoints=[],
            start_position=(0, 0),
            start_heading=0,
            finish_position=(100, 0),
            finish_heading=0,
            containment=ContainmentBoundary(
                left_points=[(-100, -100), (-100, 100), (100, 100), (100, -100)],
                right_points=[]
            ),
            obstacles=[]
        )

        results = raycast.cast_all_rays(car, track, other_cars=[])

        assert len(results) == 7
        assert all(isinstance(r, RaycastResult) for r in results)

    def test_cast_all_rays_detects_boundaries_in_all_directions(self):
        """Test that rays detect boundaries in all directions."""
        raycast = RaycastSystem(max_range=200.0)

        # Car at origin
        car = create_car_at_position(0, 0, heading=0)

        # Square boundary around car
        track = Track(
            segments=[],
            checkpoints=[],
            start_position=(0, 0),
            start_heading=0,
            finish_position=(100, 0),
            finish_heading=0,
            containment=ContainmentBoundary(
                left_points=[
                    (-100, -100), (-100, 100),  # Left wall
                    (100, 100), (100, -100),    # Right wall
                    (-100, -100)                # Close the box
                ],
                right_points=[]
            ),
            obstacles=[]
        )

        results = raycast.cast_all_rays(car, track, other_cars=[])

        # All rays should hit boundaries (since car is in center of box)
        for result in results:
            assert result.hit_type == "boundary"
            assert result.distance < 200.0  # Within max range

    def test_cast_all_rays_detects_closest_hit(self):
        """Test that rays return the closest hit when multiple objects present."""
        raycast = RaycastSystem(max_range=200.0)

        car = create_car_at_position(0, 0, heading=0)

        # Obstacle close, boundary far
        track = Track(
            segments=[],
            checkpoints=[],
            start_position=(0, 0),
            start_heading=0,
            finish_position=(100, 0),
            finish_heading=0,
            containment=ContainmentBoundary(
                left_points=[(150, -100), (150, 100)],  # Far wall
                right_points=[]
            ),
            obstacles=[
                Obstacle(position=(30, 0), radius=5, type="rock")  # Close obstacle
            ]
        )

        results = raycast.cast_all_rays(car, track, other_cars=[])

        # Forward ray (ray[0]) should hit obstacle, not boundary
        assert results[0].hit_type == "obstacle"
        assert abs(results[0].distance - 25.0) < 1.0  # Approximately 30 - 5

    def test_cast_all_rays_excludes_source_car(self):
        """Test that rays don't detect the car they're cast from."""
        raycast = RaycastSystem(max_range=200.0)

        car = create_car_at_position(0, 0, heading=0)

        track = Track(
            segments=[],
            checkpoints=[],
            start_position=(0, 0),
            start_heading=0,
            finish_position=(100, 0),
            finish_heading=0,
            containment=None,
            obstacles=[]
        )

        # Include the source car in the other_cars list
        results = raycast.cast_all_rays(car, track, other_cars=[car])

        # All rays should have max range (no hits)
        for result in results:
            assert result.hit_type is None
            assert result.distance == 200.0


class TestRayDirections:
    """Test that rays are cast in the correct directions."""

    def test_forward_ray_direction(self):
        """Test that ray[0] is cast in the forward direction."""
        raycast = RaycastSystem(max_range=100.0)

        # Car facing right (heading=0)
        car = create_car_at_position(0, 0, heading=0)

        # Wall directly ahead
        track = Track(
            segments=[],
            checkpoints=[],
            start_position=(0, 0),
            start_heading=0,
            finish_position=(100, 0),
            finish_heading=0,
            containment=ContainmentBoundary(
                left_points=[(50, -50), (50, 50)],  # Vertical wall at x=50
                right_points=[]
            ),
            obstacles=[]
        )

        results = raycast.cast_all_rays(car, track, other_cars=[])

        # Ray[0] should hit the wall
        assert results[0].hit_type == "boundary"
        assert abs(results[0].distance - 50.0) < 0.1

    def test_right_perpendicular_ray_direction(self):
        """Test that ray[3] is cast perpendicular to the right."""
        raycast = RaycastSystem(max_range=100.0)

        # Car facing right (heading=0)
        car = create_car_at_position(0, 0, heading=0)

        # Wall to the right (below, since y-axis positive is down in game coords)
        track = Track(
            segments=[],
            checkpoints=[],
            start_position=(0, 0),
            start_heading=0,
            finish_position=(100, 0),
            finish_heading=0,
            containment=ContainmentBoundary(
                left_points=[],
                right_points=[(-50, -50), (50, -50)]  # Horizontal wall at y=-50
            ),
            obstacles=[]
        )

        results = raycast.cast_all_rays(car, track, other_cars=[])

        # Ray[3] (90° right) should hit the wall
        assert results[3].hit_type == "boundary"
        assert abs(results[3].distance - 50.0) < 0.1


class TestMaxRange:
    """Test that raycasts respect the maximum range."""

    def test_max_range_limits_detection(self):
        """Test that objects beyond max range are not detected."""
        raycast = RaycastSystem(max_range=50.0)

        car = create_car_at_position(0, 0, heading=0)

        # Obstacle beyond max range
        obstacle = Obstacle(position=(100, 0), radius=10, type="rock")

        result = raycast._raycast_obstacle(
            origin=car.position,
            direction=Vector2(1, 0),
            obstacle=obstacle
        )

        assert result is None

    def test_no_hit_returns_max_range(self):
        """Test that rays with no hits return max range distance."""
        raycast = RaycastSystem(max_range=200.0)

        car = create_car_at_position(0, 0, heading=0)

        # Empty track (no boundaries or obstacles)
        track = Track(
            segments=[],
            checkpoints=[],
            start_position=(0, 0),
            start_heading=0,
            finish_position=(100, 0),
            finish_heading=0,
            containment=None,
            obstacles=[]
        )

        results = raycast.cast_all_rays(car, track, other_cars=[])

        # All rays should have max range
        for result in results:
            assert result.distance == 200.0
            assert result.hit_type is None


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_ray_origin_on_boundary(self):
        """Test ray cast from a position on the boundary."""
        raycast = RaycastSystem(max_range=100.0)

        # Car exactly on the boundary
        car = create_car_at_position(50, 0, heading=0)

        containment = ContainmentBoundary(
            left_points=[(50, -100), (50, 100)],
            right_points=[]
        )

        result = raycast._raycast_boundary(
            origin=car.position,
            direction=Vector2(1, 0),
            containment=containment
        )

        # Should either detect immediately or not at all (implementation dependent)
        # We accept either behavior as valid
        assert result is None or result.distance < 1.0

    def test_parallel_ray_and_boundary(self):
        """Test ray parallel to a boundary segment."""
        raycast = RaycastSystem(max_range=100.0)

        car = create_car_at_position(0, 0, heading=0)

        # Horizontal boundary, ray also horizontal
        containment = ContainmentBoundary(
            left_points=[(-50, 10), (50, 10)],  # Parallel to ray
            right_points=[]
        )

        result = raycast._raycast_boundary(
            origin=car.position,
            direction=Vector2(1, 0),  # Also horizontal
            containment=containment
        )

        # Parallel rays should not intersect
        assert result is None


class TestPerformance:
    """Test raycast performance with multiple cars."""

    def test_multiple_cars_performance(self):
        """Test raycast system with multiple cars (simulates multiplayer race)."""
        import time

        raycast = RaycastSystem(max_range=200.0)

        # Create 10 cars at different positions
        cars = [
            create_car_at_position(i * 20, 0, heading=0)
            for i in range(10)
        ]

        # Create track with boundaries and obstacles
        track = Track(
            segments=[],
            checkpoints=[],
            start_position=(0, 0),
            start_heading=0,
            finish_position=(200, 0),
            finish_heading=0,
            containment=ContainmentBoundary(
                left_points=[
                    (-100, -100), (-100, 100),
                    (300, 100), (300, -100)
                ],
                right_points=[]
            ),
            obstacles=[
                Obstacle(position=(i * 30, 10), radius=5, type="rock")
                for i in range(10)
            ]
        )

        # Measure time to cast all rays for all cars
        start_time = time.perf_counter()

        for car in cars:
            other_cars = [c for c in cars if c != car]
            results = raycast.cast_all_rays(car, track, other_cars)

            # Verify results
            assert len(results) == 7
            assert all(isinstance(r, RaycastResult) for r in results)

        elapsed_time = time.perf_counter() - start_time

        # With 10 cars, 7 rays each = 70 ray casts
        # Should complete in well under 100ms
        assert elapsed_time < 0.1  # 100ms

    def test_raycast_accuracy_with_multiple_objects(self):
        """Test that raycasts remain accurate with many objects in the scene."""
        raycast = RaycastSystem(max_range=200.0)

        car = create_car_at_position(0, 0, heading=0)

        # Create many obstacles at different distances
        track = Track(
            segments=[],
            checkpoints=[],
            start_position=(0, 0),
            start_heading=0,
            finish_position=(200, 0),
            finish_heading=0,
            containment=ContainmentBoundary(
                left_points=[(150, -100), (150, 100)],
                right_points=[]
            ),
            obstacles=[
                Obstacle(position=(i * 10, 0), radius=3, type="rock")
                for i in range(1, 10)  # Obstacles at 10, 20, 30, ..., 90
            ]
        )

        results = raycast.cast_all_rays(car, track, other_cars=[])

        # Forward ray should hit the closest obstacle (at x=10, minus radius)
        assert results[0].hit_type == "obstacle"
        assert abs(results[0].distance - 7.0) < 1.0  # Approximately 10 - 3
