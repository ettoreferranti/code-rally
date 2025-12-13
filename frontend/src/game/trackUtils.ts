/**
 * Track utility functions for detecting car position on track.
 */

import type { Track, Vector2, SurfaceType } from './types';

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
