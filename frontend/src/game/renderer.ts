/**
 * Canvas rendering utilities for CodeRally.
 */

import type { Track, TrackSegment, CarState, Vector2 } from './types';
import { SurfaceType } from './types';

/**
 * Surface colors for different track types.
 */
const SURFACE_COLORS: Record<SurfaceType, string> = {
  [SurfaceType.ASPHALT]: '#404040',
  [SurfaceType.WET]: '#2a4d6e',
  [SurfaceType.GRAVEL]: '#8b7355',
  [SurfaceType.ICE]: '#b0e0e6'
};

/**
 * Camera system for smooth following.
 */
export class Camera {
  x: number = 0;
  y: number = 0;
  zoom: number = 1.0;

  /**
   * Update camera to follow a target position smoothly.
   */
  follow(targetX: number, targetY: number, smoothing: number = 0.1): void {
    this.x += (targetX - this.x) * smoothing;
    this.y += (targetY - this.y) * smoothing;
  }

  /**
   * Apply camera transform to canvas context.
   */
  apply(ctx: CanvasRenderingContext2D, canvas: HTMLCanvasElement): void {
    ctx.setTransform(1, 0, 0, 1, 0, 0); // Reset transform
    ctx.translate(canvas.width / 2, canvas.height / 2);
    ctx.scale(this.zoom, this.zoom);
    ctx.translate(-this.x, -this.y);
  }
}

/**
 * Calculate point on cubic bezier curve.
 */
function bezierPoint(
  p0: [number, number],
  p1: [number, number],
  p2: [number, number],
  p3: [number, number],
  t: number
): [number, number] {
  const mt = 1 - t;
  const mt2 = mt * mt;
  const mt3 = mt2 * mt;
  const t2 = t * t;
  const t3 = t2 * t;

  const x = mt3 * p0[0] + 3 * mt2 * t * p1[0] + 3 * mt * t2 * p2[0] + t3 * p3[0];
  const y = mt3 * p0[1] + 3 * mt2 * t * p1[1] + 3 * mt * t2 * p2[1] + t3 * p3[1];

  return [x, y];
}

/**
 * Render a track segment.
 */
function renderSegment(
  ctx: CanvasRenderingContext2D,
  segment: TrackSegment,
  drawBoundaries: boolean = true
): void {
  const isStraight = !segment.control1 || !segment.control2;

  // Generate points along the segment
  const numPoints = isStraight ? 2 : 50;
  const points: [number, number][] = [];

  for (let i = 0; i <= numPoints; i++) {
    const t = i / numPoints;

    if (isStraight) {
      const x = segment.start.x + t * (segment.end.x - segment.start.x);
      const y = segment.start.y + t * (segment.end.y - segment.start.y);
      points.push([x, y]);
    } else {
      const point = bezierPoint(
        [segment.start.x, segment.start.y],
        segment.control1!,
        segment.control2!,
        [segment.end.x, segment.end.y],
        t
      );
      points.push(point);
    }
  }

  // Draw track surface (thick line)
  const color = SURFACE_COLORS[segment.start.surface] || SURFACE_COLORS[SurfaceType.ASPHALT];
  ctx.strokeStyle = color;
  ctx.lineWidth = segment.start.width;
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';

  ctx.beginPath();
  ctx.moveTo(points[0][0], points[0][1]);
  for (let i = 1; i < points.length; i++) {
    ctx.lineTo(points[i][0], points[i][1]);
  }
  ctx.stroke();

  // Draw boundaries (edges)
  if (drawBoundaries) {
    ctx.strokeStyle = '#ffffff';
    ctx.lineWidth = 2;

    // Calculate perpendicular offset for boundaries
    for (let side of [-1, 1]) {
      ctx.beginPath();

      for (let i = 0; i < points.length; i++) {
        const [x, y] = points[i];

        // Calculate perpendicular direction
        let dx: number, dy: number;
        if (i === 0) {
          dx = points[1][0] - points[0][0];
          dy = points[1][1] - points[0][1];
        } else {
          dx = points[i][0] - points[i - 1][0];
          dy = points[i][1] - points[i - 1][1];
        }

        const length = Math.sqrt(dx * dx + dy * dy);
        if (length > 0) {
          dx /= length;
          dy /= length;
        }

        // Perpendicular offset
        const perpX = -dy * side * segment.start.width / 2;
        const perpY = dx * side * segment.start.width / 2;

        if (i === 0) {
          ctx.moveTo(x + perpX, y + perpY);
        } else {
          ctx.lineTo(x + perpX, y + perpY);
        }
      }

      ctx.stroke();
    }
  }
}

/**
 * Render containment boundaries (outer walls).
 */
function renderContainment(ctx: CanvasRenderingContext2D, track: Track): void {
  if (!track.containment) return;

  const { left_points, right_points } = track.containment;

  // Draw containment walls as thick brown/gray lines
  ctx.strokeStyle = '#6b5b47';
  ctx.lineWidth = 8;
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';

  // Draw left wall
  ctx.beginPath();
  ctx.moveTo(left_points[0][0], left_points[0][1]);
  for (let i = 1; i < left_points.length; i++) {
    ctx.lineTo(left_points[i][0], left_points[i][1]);
  }
  ctx.stroke();

  // Draw right wall
  ctx.beginPath();
  ctx.moveTo(right_points[0][0], right_points[0][1]);
  for (let i = 1; i < right_points.length; i++) {
    ctx.lineTo(right_points[i][0], right_points[i][1]);
  }
  ctx.stroke();
}

/**
 * Render obstacles in off-road areas.
 */
function renderObstacles(ctx: CanvasRenderingContext2D, track: Track): void {
  if (!track.obstacles || track.obstacles.length === 0) return;

  for (const obstacle of track.obstacles) {
    const [x, y] = obstacle.position;
    const radius = obstacle.radius;

    // Choose color based on obstacle type
    let color: string;
    switch (obstacle.type) {
      case 'rock':
        color = '#5a5a5a';
        break;
      case 'tree':
        color = '#2d5016';
        break;
      case 'building':
        color = '#8b4513';
        break;
      default:
        color = '#666666';
    }

    // Draw obstacle as filled circle
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.arc(x, y, radius, 0, Math.PI * 2);
    ctx.fill();

    // Draw outline
    ctx.strokeStyle = '#000000';
    ctx.lineWidth = 2;
    ctx.stroke();
  }
}

/**
 * Render the entire track.
 */
export function renderTrack(ctx: CanvasRenderingContext2D, track: Track): void {
  // Draw containment boundaries first (background)
  renderContainment(ctx, track);

  // Draw all segments
  for (const segment of track.segments) {
    renderSegment(ctx, segment);
  }

  // Draw obstacles AFTER track so they're visible
  renderObstacles(ctx, track);

  // Draw checkpoints
  ctx.strokeStyle = '#ff0000';
  ctx.lineWidth = 3;
  ctx.globalAlpha = 0.5;

  for (const checkpoint of track.checkpoints) {
    const [x, y] = checkpoint.position;
    const angle = checkpoint.angle + Math.PI / 2; // Perpendicular
    const length = checkpoint.width / 2;

    const x1 = x + length * Math.cos(angle);
    const y1 = y + length * Math.sin(angle);
    const x2 = x - length * Math.cos(angle);
    const y2 = y - length * Math.sin(angle);

    ctx.beginPath();
    ctx.moveTo(x1, y1);
    ctx.lineTo(x2, y2);
    ctx.stroke();
  }

  ctx.globalAlpha = 1.0;

  // Draw start position
  const [startX, startY] = track.start_position;
  ctx.fillStyle = '#00ff00';
  ctx.beginPath();
  ctx.arc(startX, startY, 10, 0, Math.PI * 2);
  ctx.fill();
}

/**
 * Render a car.
 */
export function renderCar(
  ctx: CanvasRenderingContext2D,
  car: CarState,
  color: string = '#ff0000'
): void {
  ctx.save();

  // Translate to car position and rotate to heading
  ctx.translate(car.position.x, car.position.y);
  ctx.rotate(car.heading);

  // Car dimensions (width is along direction of travel = +x in local coords)
  const width = 30;
  const height = 20;

  // Draw car body (rectangle along x-axis)
  ctx.fillStyle = color;
  ctx.fillRect(-width / 2, -height / 2, width, height);

  // Draw car outline
  ctx.strokeStyle = '#ffffff';
  ctx.lineWidth = 2;
  ctx.strokeRect(-width / 2, -height / 2, width, height);

  // Draw heading indicator (triangle pointing in +x direction)
  ctx.fillStyle = '#ffffff';
  ctx.beginPath();
  ctx.moveTo(width / 2 + 5, 0);
  ctx.lineTo(width / 2 - 3, -height / 4);
  ctx.lineTo(width / 2 - 3, height / 4);
  ctx.closePath();
  ctx.fill();

  // Draw drift indicator if drifting
  if (car.is_drifting) {
    ctx.strokeStyle = '#ffaa00';
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.arc(0, 0, 25, 0, Math.PI * 2);
    ctx.stroke();
  }

  ctx.restore();
}

/**
 * Clear the canvas.
 */
export function clearCanvas(ctx: CanvasRenderingContext2D, canvas: HTMLCanvasElement): void {
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.fillStyle = '#1a1a1a'; // Dark background
  ctx.fillRect(0, 0, canvas.width, canvas.height);
}
