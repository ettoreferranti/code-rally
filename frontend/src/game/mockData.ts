/**
 * Mock game data for testing rendering.
 */

import type { GameState } from './types';
import { SurfaceType } from './types';

/**
 * Create a simple circular track for demonstration.
 */
export function createMockGameState(): GameState {
  const radius = 300;
  const numSegments = 8;
  const segments = [];
  const checkpoints = [];

  for (let i = 0; i < numSegments; i++) {
    const angle1 = (2 * Math.PI * i) / numSegments;
    const angle2 = (2 * Math.PI * (i + 1)) / numSegments;

    const x1 = radius * Math.cos(angle1);
    const y1 = radius * Math.sin(angle1);
    const x2 = radius * Math.cos(angle2);
    const y2 = radius * Math.sin(angle2);

    // Control points for bezier curve
    const controlDist = radius * 0.4;
    const control1X = x1 + controlDist * Math.cos(angle1 + Math.PI / 2);
    const control1Y = y1 + controlDist * Math.sin(angle1 + Math.PI / 2);
    const control2X = x2 + controlDist * Math.cos(angle2 + Math.PI / 2);
    const control2Y = y2 + controlDist * Math.sin(angle2 + Math.PI / 2);

    // Vary surface types
    const surfaceTypes = [
      SurfaceType.ASPHALT,
      SurfaceType.ASPHALT,
      SurfaceType.WET,
      SurfaceType.ASPHALT,
      SurfaceType.GRAVEL,
      SurfaceType.ASPHALT,
      SurfaceType.ASPHALT,
      SurfaceType.ICE
    ];

    segments.push({
      start: {
        x: x1,
        y: y1,
        width: 80,
        surface: surfaceTypes[i]
      },
      end: {
        x: x2,
        y: y2,
        width: 80,
        surface: surfaceTypes[i]
      },
      control1: [control1X, control1Y] as [number, number],
      control2: [control2X, control2Y] as [number, number]
    });

    // Add checkpoint at midpoint
    const checkpointAngle = (angle1 + angle2) / 2;
    checkpoints.push({
      position: [
        radius * Math.cos(checkpointAngle),
        radius * Math.sin(checkpointAngle)
      ] as [number, number],
      angle: checkpointAngle,
      width: 80,
      index: i
    });
  }

  // Create a car at the start (right side of circle, facing downward)
  const car = {
    position: { x: radius, y: 0 },
    velocity: { x: 0, y: 0 },
    heading: 0, // Will be updated to correct direction on first update
    angular_velocity: 0,
    is_drifting: false,
    drift_angle: 0
  };

  return {
    track: {
      segments,
      checkpoints,
      start_position: [radius, 0],
      start_heading: Math.PI / 2,
      total_length: 2 * Math.PI * radius
    },
    cars: [car],
    tick: 0
  };
}

/**
 * Simulate car movement in a circle for demonstration.
 */
export function updateMockCar(gameState: GameState, deltaTime: number): GameState {
  if (gameState.cars.length === 0) return gameState;

  const car = gameState.cars[0];
  const speed = 100; // units per second
  const angularSpeed = 0.5; // radians per second

  // Move car in a circle
  // car.heading stores the angle position around the circle
  const newHeading = car.heading + angularSpeed * deltaTime;
  const radius = 300;

  return {
    ...gameState,
    cars: [
      {
        ...car,
        heading: newHeading,
        position: {
          x: radius * Math.cos(newHeading),
          y: radius * Math.sin(newHeading)
        },
        velocity: {
          x: -speed * Math.sin(newHeading),
          y: speed * Math.cos(newHeading)
        },
        is_drifting: Math.abs(angularSpeed) > 0.3
      }
    ],
    tick: gameState.tick + 1
  };
}
