/**
 * Mock game data for testing rendering.
 */

import type { GameState } from './types';
import { SurfaceType } from './types';

/**
 * Create a point-to-point rally stage for demonstration.
 */
export function createMockGameState(): GameState {
  const segments = [];
  const checkpoints = [];

  // Define control points for a serpentine rally stage
  // Stage goes from top-left to bottom-right with curves
  // More waypoints for a longer, more varied stage
  const stagePoints = [
    // Section 1: Fast asphalt opening (4 waypoints = 3 segments)
    { x: -500, y: -400 },  // Start
    { x: -300, y: -350 },
    { x: -100, y: -300 },
    { x: 100, y: -250 },

    // Section 2: Technical wet section (3 waypoints = 2 segments)
    { x: 300, y: -200 },
    { x: 400, y: -50 },

    // Section 3: Long gravel hairpin (4 waypoints = 3 segments)
    { x: 350, y: 100 },
    { x: 200, y: 200 },
    { x: 0, y: 250 },

    // Section 4: Tricky ice section (3 waypoints = 2 segments)
    { x: -200, y: 300 },
    { x: -350, y: 400 },

    // Section 5: Final asphalt sprint (3 waypoints = 2 segments)
    { x: -400, y: 500 },
    { x: -300, y: 600 },   // Finish
  ];

  // Surface types for each segment - grouped into sections
  // This creates longer stretches of consistent surface
  const surfaceTypes = [
    // Section 1: Asphalt opening (3 segments)
    SurfaceType.ASPHALT,
    SurfaceType.ASPHALT,
    SurfaceType.ASPHALT,

    // Section 2: Wet technical (2 segments)
    SurfaceType.WET,
    SurfaceType.WET,

    // Section 3: Gravel hairpin (3 segments)
    SurfaceType.GRAVEL,
    SurfaceType.GRAVEL,
    SurfaceType.GRAVEL,

    // Section 4: Ice challenge (2 segments)
    SurfaceType.ICE,
    SurfaceType.ICE,

    // Section 5: Asphalt finish (2 segments)
    SurfaceType.ASPHALT,
    SurfaceType.ASPHALT,
  ];

  // Define which segments should be curved vs straight
  // 0 = straight, values > 0 = curve intensity
  const curveIntensities = [
    0.2,   // Section 1: Gentle opening curve
    0,     // Straight
    0.15,  // Gentle curve

    0.4,   // Section 2: Sharp wet corner
    0.3,   // Medium curve

    0.5,   // Section 3: Tight gravel hairpin
    0.45,  // Still tight
    0.35,  // Easing out

    0.2,   // Section 4: Gentle ice curve (dangerous if sharp!)
    0.25,  // Medium ice curve

    0,     // Section 5: Straight sprint
    0.15,  // Gentle finish curve
  ];

  // Create segments between points
  for (let i = 0; i < stagePoints.length - 1; i++) {
    const p1 = stagePoints[i];
    const p2 = stagePoints[i + 1];

    const dx = p2.x - p1.x;
    const dy = p2.y - p1.y;

    let control1 = undefined;
    let control2 = undefined;

    // Only add bezier curves if intensity > 0
    if (curveIntensities[i] > 0) {
      // Perpendicular offset for curve
      const offsetX = -dy * curveIntensities[i];
      const offsetY = dx * curveIntensities[i];

      const control1X = p1.x + dx * 0.33 + offsetX;
      const control1Y = p1.y + dy * 0.33 + offsetY;
      const control2X = p1.x + dx * 0.66 + offsetX;
      const control2Y = p1.y + dy * 0.66 + offsetY;

      control1 = [control1X, control1Y] as [number, number];
      control2 = [control2X, control2Y] as [number, number];
    }

    segments.push({
      start: {
        x: p1.x,
        y: p1.y,
        width: 160,
        surface: surfaceTypes[i]
      },
      end: {
        x: p2.x,
        y: p2.y,
        width: 160,
        surface: surfaceTypes[i]
      },
      control1,
      control2
    });

    // Add checkpoint at segment midpoint
    const midX = (p1.x + p2.x) / 2;
    const midY = (p1.y + p2.y) / 2;
    const angle = Math.atan2(dy, dx);

    checkpoints.push({
      position: [midX, midY] as [number, number],
      angle: angle,
      width: 160,
      index: i
    });
  }

  // Calculate approximate stage length
  let totalLength = 0;
  for (let i = 0; i < stagePoints.length - 1; i++) {
    const p1 = stagePoints[i];
    const p2 = stagePoints[i + 1];
    const dx = p2.x - p1.x;
    const dy = p2.y - p1.y;
    totalLength += Math.sqrt(dx * dx + dy * dy);
  }

  const startPos = stagePoints[0];
  const finishPos = stagePoints[stagePoints.length - 1];
  const startHeading = Math.atan2(
    stagePoints[1].y - stagePoints[0].y,
    stagePoints[1].x - stagePoints[0].x
  );
  const finishHeading = Math.atan2(
    finishPos.y - stagePoints[stagePoints.length - 2].y,
    finishPos.x - stagePoints[stagePoints.length - 2].x
  );

  // Create a car at the start position
  const car = {
    position: { x: startPos.x, y: startPos.y },
    velocity: { x: 0, y: 0 },
    heading: startHeading,
    angular_velocity: 0,
    is_drifting: false,
    drift_angle: 0,
    throttle: 0,
    is_off_track: false
  };

  return {
    track: {
      segments,
      checkpoints,
      start_position: [startPos.x, startPos.y],
      start_heading: startHeading,
      finish_position: [finishPos.x, finishPos.y],
      finish_heading: finishHeading,
      total_length: totalLength,
      is_looping: false
    },
    cars: [car],
    tick: 0,
    raceInfo: {
      currentCheckpoint: 0,
      totalCheckpoints: checkpoints.length,
      isFinished: false,
      finishTime: null,
      startTime: Date.now() / 1000  // Current time in seconds
    }
  };
}

/**
 * Simple demonstration function - no longer needed as we use physics engine.
 * Kept for backwards compatibility.
 */
export function updateMockCar(gameState: GameState, deltaTime: number): GameState {
  // Physics engine handles all updates now
  return gameState;
}
