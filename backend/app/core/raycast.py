"""
Raycast system for CodeRally bot vision.

Provides 7-direction raycasts from car position to detect:
- Track boundaries (containment walls)
- Other cars
- Obstacles

Used to populate BotRaycast sensor data for bot decision-making.
"""

import math
from dataclasses import dataclass
from typing import List, Optional, Tuple

from app.core.physics import Vector2, CarState
from app.core.track import Track, Obstacle, ContainmentBoundary
from app.config import get_settings


@dataclass
class RaycastResult:
    """
    Result of a single raycast.

    Attributes:
        distance: Distance to hit point (or max_range if no hit)
        hit_type: Type of object hit ("boundary", "car", "obstacle", or None)
        hit_position: Position where ray hit (x, y) or None if no hit
    """
    distance: float
    hit_type: Optional[str] = None
    hit_position: Optional[Tuple[float, float]] = None


class RaycastSystem:
    """
    Raycast vision system for bots.

    Casts 7 rays in different directions from a car to detect obstacles:
    - ray[0]: forward (0°)
    - ray[1]: 30° right
    - ray[2]: 60° right
    - ray[3]: 90° right (perpendicular)
    - ray[4]: 60° left
    - ray[5]: 30° left
    - ray[6]: 90° left
    """

    # Ray directions in radians (relative to car heading)
    RAY_ANGLES = [
        0.0,                  # ray[0]: forward
        -math.pi / 6,         # ray[1]: 30° right
        -math.pi / 3,         # ray[2]: 60° right
        -math.pi / 2,         # ray[3]: 90° right
        math.pi / 3,          # ray[4]: 60° left
        math.pi / 6,          # ray[5]: 30° left
        math.pi / 2,          # ray[6]: 90° left
    ]

    def __init__(self, max_range: float = 200.0):
        """
        Initialize raycast system.

        Args:
            max_range: Maximum distance for raycasts (default 200 units)
        """
        self.settings = get_settings()
        self.max_range = max_range

    def cast_all_rays(
        self,
        car: CarState,
        track: Track,
        other_cars: List[CarState]
    ) -> List[RaycastResult]:
        """
        Cast all 7 rays from a car position.

        Args:
            car: The car to cast rays from
            track: Track with boundaries and obstacles
            other_cars: List of other cars to detect

        Returns:
            List of 7 RaycastResult objects, one for each ray direction
        """
        results = []

        for angle_offset in self.RAY_ANGLES:
            # Calculate ray direction in world space
            ray_angle = car.heading + angle_offset
            ray_dir = Vector2(math.cos(ray_angle), math.sin(ray_angle))

            # Cast the ray
            result = self._cast_ray(
                origin=car.position,
                direction=ray_dir,
                track=track,
                other_cars=other_cars,
                source_car=car
            )

            results.append(result)

        return results

    def _cast_ray(
        self,
        origin: Vector2,
        direction: Vector2,
        track: Track,
        other_cars: List[CarState],
        source_car: CarState
    ) -> RaycastResult:
        """
        Cast a single ray and find the closest hit.

        Args:
            origin: Ray origin position
            direction: Ray direction (normalized vector)
            track: Track with boundaries and obstacles
            other_cars: List of other cars to detect
            source_car: The car casting the ray (to exclude self)

        Returns:
            RaycastResult with distance and hit type
        """
        closest_hit = RaycastResult(distance=self.max_range, hit_type=None)

        # Check boundary hits
        if track.containment:
            boundary_hit = self._raycast_boundary(origin, direction, track.containment)
            if boundary_hit and boundary_hit.distance < closest_hit.distance:
                closest_hit = boundary_hit

        # Check obstacle hits
        for obstacle in track.obstacles:
            obstacle_hit = self._raycast_obstacle(origin, direction, obstacle)
            if obstacle_hit and obstacle_hit.distance < closest_hit.distance:
                closest_hit = obstacle_hit

        # Check car hits
        for other_car in other_cars:
            # Don't detect self
            if other_car.position == source_car.position:
                continue

            car_hit = self._raycast_car(origin, direction, other_car)
            if car_hit and car_hit.distance < closest_hit.distance:
                closest_hit = car_hit

        return closest_hit

    def _raycast_boundary(
        self,
        origin: Vector2,
        direction: Vector2,
        containment: ContainmentBoundary
    ) -> Optional[RaycastResult]:
        """
        Cast ray against containment boundaries.

        Args:
            origin: Ray origin
            direction: Ray direction
            containment: Containment boundary with left and right points

        Returns:
            RaycastResult if hit, None otherwise
        """
        closest_hit = None
        min_distance = self.max_range

        # Check all boundary segments
        all_boundary_points = containment.left_points + containment.right_points

        for i in range(len(all_boundary_points) - 1):
            p1 = all_boundary_points[i]
            p2 = all_boundary_points[i + 1]

            # Ray-line segment intersection
            hit_point, distance = self._ray_segment_intersection(
                ray_origin=origin,
                ray_dir=direction,
                seg_p1=Vector2(p1[0], p1[1]),
                seg_p2=Vector2(p2[0], p2[1])
            )

            if hit_point is not None and distance < min_distance:
                min_distance = distance
                closest_hit = RaycastResult(
                    distance=distance,
                    hit_type="boundary",
                    hit_position=(hit_point.x, hit_point.y)
                )

        return closest_hit

    def _raycast_obstacle(
        self,
        origin: Vector2,
        direction: Vector2,
        obstacle: Obstacle
    ) -> Optional[RaycastResult]:
        """
        Cast ray against a circular obstacle.

        Args:
            origin: Ray origin
            direction: Ray direction
            obstacle: Obstacle to test against

        Returns:
            RaycastResult if hit, None otherwise
        """
        # Ray-circle intersection
        obs_pos = Vector2(obstacle.position[0], obstacle.position[1])

        # Vector from ray origin to circle center
        to_circle = obs_pos - origin

        # Project onto ray direction
        proj_length = to_circle.dot(direction)

        # If projection is negative, circle is behind ray origin
        if proj_length < 0:
            return None

        # Find closest point on ray to circle center
        closest_point = origin + direction * proj_length

        # Distance from circle center to closest point
        dist_to_ray = (obs_pos - closest_point).magnitude()

        # Check if ray intersects circle
        if dist_to_ray > obstacle.radius:
            return None

        # Calculate intersection distance
        # Use Pythagorean theorem
        chord_half_length = math.sqrt(obstacle.radius ** 2 - dist_to_ray ** 2)
        hit_distance = proj_length - chord_half_length

        if hit_distance < 0 or hit_distance > self.max_range:
            return None

        hit_pos = origin + direction * hit_distance

        return RaycastResult(
            distance=hit_distance,
            hit_type="obstacle",
            hit_position=(hit_pos.x, hit_pos.y)
        )

    def _raycast_car(
        self,
        origin: Vector2,
        direction: Vector2,
        car: CarState
    ) -> Optional[RaycastResult]:
        """
        Cast ray against another car (treated as circle).

        Args:
            origin: Ray origin
            direction: Ray direction
            car: Car to test against

        Returns:
            RaycastResult if hit, None otherwise
        """
        # Cars are treated as circles with radius
        car_radius = 10.0  # TODO: Make this configurable

        # Ray-circle intersection (same as obstacle)
        car_pos = car.position

        # Vector from ray origin to car center
        to_car = car_pos - origin

        # Project onto ray direction
        proj_length = to_car.dot(direction)

        # If projection is negative, car is behind ray origin
        if proj_length < 0:
            return None

        # Find closest point on ray to car center
        closest_point = origin + direction * proj_length

        # Distance from car center to closest point
        dist_to_ray = (car_pos - closest_point).magnitude()

        # Check if ray intersects car
        if dist_to_ray > car_radius:
            return None

        # Calculate intersection distance
        chord_half_length = math.sqrt(car_radius ** 2 - dist_to_ray ** 2)
        hit_distance = proj_length - chord_half_length

        if hit_distance < 0 or hit_distance > self.max_range:
            return None

        hit_pos = origin + direction * hit_distance

        return RaycastResult(
            distance=hit_distance,
            hit_type="car",
            hit_position=(hit_pos.x, hit_pos.y)
        )

    def _ray_segment_intersection(
        self,
        ray_origin: Vector2,
        ray_dir: Vector2,
        seg_p1: Vector2,
        seg_p2: Vector2
    ) -> Tuple[Optional[Vector2], float]:
        """
        Calculate intersection between a ray and a line segment.

        Args:
            ray_origin: Origin of the ray
            ray_dir: Direction of the ray (should be normalized)
            seg_p1: First endpoint of line segment
            seg_p2: Second endpoint of line segment

        Returns:
            Tuple of (hit_point, distance) or (None, infinity) if no hit
        """
        # Ray: P = ray_origin + t * ray_dir (t >= 0)
        # Segment: Q = seg_p1 + s * (seg_p2 - seg_p1) (0 <= s <= 1)

        # Solve for intersection:
        # ray_origin + t * ray_dir = seg_p1 + s * seg_dir
        # Rearranged: t * ray_dir - s * seg_dir = seg_p1 - ray_origin

        seg_dir = seg_p2 - seg_p1
        diff = seg_p1 - ray_origin

        # Use 2D cross product to solve the system
        # cross(ray_dir, seg_dir) = ray_dir.x * seg_dir.y - ray_dir.y * seg_dir.x
        cross_ray_seg = ray_dir.x * seg_dir.y - ray_dir.y * seg_dir.x

        # Parallel rays don't intersect
        if abs(cross_ray_seg) < 1e-10:
            return (None, float('inf'))

        # Solve for t and s
        cross_diff_seg = diff.x * seg_dir.y - diff.y * seg_dir.x
        cross_diff_ray = diff.x * ray_dir.y - diff.y * ray_dir.x

        t = cross_diff_seg / cross_ray_seg
        s = cross_diff_ray / cross_ray_seg

        # Check if intersection is valid:
        # t >= 0 (in front of ray)
        # 0 <= s <= 1 (on line segment)
        # t <= max_range (within detection range)
        if t >= 0 and 0 <= s <= 1 and t <= self.max_range:
            hit_point = ray_origin + ray_dir * t
            return (hit_point, t)

        return (None, float('inf'))
