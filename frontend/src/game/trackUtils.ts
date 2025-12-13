/**
 * Track utility functions for detecting car position on track.
 */

import type { Track, Vector2, SurfaceType } from './types';

/**
 * Represents a boundary edge of the track.
 */
export interface BoundaryEdge {
  start: Vector2;
  end: Vector2;
  normal: Vector2;  // Outward-facing normal (points away from track center)
}

/**
 * Result of a collision check with track boundaries.
 */
export interface CollisionResult {
  collided: boolean;
  normal?: Vector2;  // Normal vector at collision point
  penetration?: number;  // How far the car has penetrated the boundary
  point?: Vector2;  // Collision point
}

/**
 * Check if a position is within track boundaries.
 * Returns object with on-track status and distance from track centerline.
 */
export function isOnTrack(track: Track, position: Vector2): { onTrack: boolean; distance: number; trackWidth: number } {
  let closestDistance = Infinity;
  let closestWidth = 160; // Default width

  // Check distance to each segment
  for (const segment of track.segments) {
    // Sample points along the segment
    const numSamples = 10;
    for (let i = 0; i <= numSamples; i++) {
      const t = i / numSamples;

      let point: Vector2;
      if (segment.control1 && segment.control2) {
        // Bezier curve
        point = bezierPoint(
          { x: segment.start.x, y: segment.start.y },
          segment.control1,
          segment.control2,
          { x: segment.end.x, y: segment.end.y },
          t
        );
      } else {
        // Straight line
        point = {
          x: segment.start.x + t * (segment.end.x - segment.start.x),
          y: segment.start.y + t * (segment.end.y - segment.start.y)
        };
      }

      // Calculate distance from car to this point
      const dx = position.x - point.x;
      const dy = position.y - point.y;
      const distance = Math.sqrt(dx * dx + dy * dy);

      if (distance < closestDistance) {
        closestDistance = distance;
        closestWidth = segment.start.width;
      }
    }
  }

  // Car is on track if within half the track width
  const onTrack = closestDistance <= closestWidth / 2;

  return { onTrack, distance: closestDistance, trackWidth: closestWidth };
}

/**
 * Find the closest point on the track to a given position.
 * Returns the surface type at that point.
 */
export function getSurfaceAtPosition(track: Track, position: Vector2): SurfaceType {
  let closestDistance = Infinity;
  let closestSurface = track.segments[0]?.start.surface;

  // Check distance to each segment
  for (const segment of track.segments) {
    // Sample fewer points for performance (5 instead of 10)
    const numSamples = 5;
    for (let i = 0; i <= numSamples; i++) {
      const t = i / numSamples;

      let point: Vector2;
      if (segment.control1 && segment.control2) {
        // Bezier curve
        point = bezierPoint(
          { x: segment.start.x, y: segment.start.y },
          segment.control1,
          segment.control2,
          { x: segment.end.x, y: segment.end.y },
          t
        );
      } else {
        // Straight line
        point = {
          x: segment.start.x + t * (segment.end.x - segment.start.x),
          y: segment.start.y + t * (segment.end.y - segment.start.y)
        };
      }

      // Calculate distance from car to this point
      const dx = position.x - point.x;
      const dy = position.y - point.y;
      const distance = Math.sqrt(dx * dx + dy * dy);

      if (distance < closestDistance) {
        closestDistance = distance;
        closestSurface = segment.start.surface;
      }
    }
  }

  return closestSurface;
}

/**
 * Calculate point on cubic bezier curve.
 */
function bezierPoint(
  p0: Vector2,
  p1: [number, number],
  p2: [number, number],
  p3: Vector2,
  t: number
): Vector2 {
  const mt = 1 - t;
  const mt2 = mt * mt;
  const mt3 = mt2 * mt;
  const t2 = t * t;
  const t3 = t2 * t;

  return {
    x: mt3 * p0.x + 3 * mt2 * t * p1[0] + 3 * mt * t2 * p2[0] + t3 * p3.x,
    y: mt3 * p0.y + 3 * mt2 * t * p1[1] + 3 * mt * t2 * p2[1] + t3 * p3.y
  };
}

/**
 * Check for collision with containment boundaries (outer walls).
 * If no containment data is available, returns no collision.
 */
export function checkBoundaryCollision(track: Track, position: Vector2, carRadius: number = 10): CollisionResult {
  const CAR_RADIUS = carRadius;

  // If no containment boundaries, no collision
  if (!track.containment) {
    return { collided: false };
  }

  const { left_points, right_points } = track.containment;

  // Check left wall
  for (let i = 0; i < left_points.length - 1; i++) {
    const p1 = { x: left_points[i][0], y: left_points[i][1] };
    const p2 = { x: left_points[i + 1][0], y: left_points[i + 1][1] };

    const collision = pointToLineSegmentDistance(position, p1, p2, CAR_RADIUS);

    if (collision.collided) {
      return collision;
    }
  }

  // Check right wall
  for (let i = 0; i < right_points.length - 1; i++) {
    const p1 = { x: right_points[i][0], y: right_points[i][1] };
    const p2 = { x: right_points[i + 1][0], y: right_points[i + 1][1] };

    const collision = pointToLineSegmentDistance(position, p1, p2, CAR_RADIUS);

    if (collision.collided) {
      return collision;
    }
  }

  return { collided: false };
}

/**
 * Check for collision with obstacles.
 * Returns the first obstacle collision detected.
 */
export function checkObstacleCollision(track: Track, position: Vector2, carRadius: number = 10): CollisionResult {
  const CAR_RADIUS = carRadius;

  if (!track.obstacles || track.obstacles.length === 0) {
    return { collided: false };
  }

  for (const obstacle of track.obstacles) {
    const dx = position.x - obstacle.position[0];
    const dy = position.y - obstacle.position[1];
    const distance = Math.sqrt(dx * dx + dy * dy);

    const collisionDistance = CAR_RADIUS + obstacle.radius;

    if (distance < collisionDistance) {
      // Calculate collision normal (pointing from obstacle to car)
      const normal = distance > 0
        ? { x: dx / distance, y: dy / distance }
        : { x: 1, y: 0 };  // Default if exactly on top

      return {
        collided: true,
        normal,
        penetration: collisionDistance - distance,
        point: { x: obstacle.position[0], y: obstacle.position[1] }
      };
    }
  }

  return { collided: false };
}

/**
 * Calculate distance from point to line segment and check for collision.
 */
function pointToLineSegmentDistance(
  point: Vector2,
  lineStart: Vector2,
  lineEnd: Vector2,
  threshold: number
): CollisionResult {
  const dx = lineEnd.x - lineStart.x;
  const dy = lineEnd.y - lineStart.y;
  const lengthSquared = dx * dx + dy * dy;

  if (lengthSquared === 0) {
    // Line segment is a point
    const distX = point.x - lineStart.x;
    const distY = point.y - lineStart.y;
    const distance = Math.sqrt(distX * distX + distY * distY);

    if (distance < threshold) {
      const normal = distance > 0 ? { x: distX / distance, y: distY / distance } : { x: 1, y: 0 };
      return {
        collided: true,
        normal,
        penetration: threshold - distance,
        point: lineStart
      };
    }
    return { collided: false };
  }

  // Calculate projection of point onto line segment
  const t = Math.max(0, Math.min(1,
    ((point.x - lineStart.x) * dx + (point.y - lineStart.y) * dy) / lengthSquared
  ));

  // Closest point on line segment
  const closest = {
    x: lineStart.x + t * dx,
    y: lineStart.y + t * dy
  };

  // Distance from point to closest point
  const distX = point.x - closest.x;
  const distY = point.y - closest.y;
  const distance = Math.sqrt(distX * distX + distY * distY);

  if (distance < threshold) {
    // Collision detected
    const normal = distance > 0 ? { x: distX / distance, y: distY / distance } : { x: 0, y: 1 };
    return {
      collided: true,
      normal,
      penetration: threshold - distance,
      point: closest
    };
  }

  return { collided: false };
}
