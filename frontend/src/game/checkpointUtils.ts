/**
 * Checkpoint detection and progress tracking utilities.
 */

import type { Vector2, Checkpoint, GameState } from './types';

/**
 * Check if a car has crossed a checkpoint line.
 * Uses line intersection detection between car's previous and current position.
 */
export function hasPassedCheckpoint(
  prevPos: Vector2,
  currentPos: Vector2,
  checkpoint: Checkpoint
): boolean {
  const [cpX, cpY] = checkpoint.position;
  const cpAngle = checkpoint.angle;
  const cpWidth = checkpoint.width;

  // Calculate checkpoint line endpoints (perpendicular to checkpoint angle)
  const perpAngle = cpAngle + Math.PI / 2;
  const halfWidth = cpWidth / 2;

  const cp1X = cpX + Math.cos(perpAngle) * halfWidth;
  const cp1Y = cpY + Math.sin(perpAngle) * halfWidth;
  const cp2X = cpX - Math.cos(perpAngle) * halfWidth;
  const cp2Y = cpY - Math.sin(perpAngle) * halfWidth;

  // Check if line segments intersect (car path vs checkpoint line)
  return lineSegmentsIntersect(
    prevPos.x, prevPos.y,
    currentPos.x, currentPos.y,
    cp1X, cp1Y,
    cp2X, cp2Y
  );
}

/**
 * Check if two line segments intersect.
 */
function lineSegmentsIntersect(
  x1: number, y1: number,
  x2: number, y2: number,
  x3: number, y3: number,
  x4: number, y4: number
): boolean {
  const denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4);

  if (Math.abs(denom) < 0.0001) {
    return false; // Lines are parallel
  }

  const t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / denom;
  const u = -((x1 - x2) * (y1 - y3) - (y1 - y2) * (x1 - x3)) / denom;

  return t >= 0 && t <= 1 && u >= 0 && u <= 1;
}

/**
 * Update race info based on checkpoint crossings.
 */
export function updateCheckpointProgress(
  gameState: GameState,
  prevCarPos: Vector2
): GameState {
  if (gameState.raceInfo.isFinished) {
    return gameState; // Race already finished
  }

  const car = gameState.cars[0];
  const currentCheckpoint = gameState.raceInfo.currentCheckpoint;

  // Check if car passed the next checkpoint
  if (currentCheckpoint < gameState.track.checkpoints.length) {
    const checkpoint = gameState.track.checkpoints[currentCheckpoint];

    if (hasPassedCheckpoint(prevCarPos, car.position, checkpoint)) {
      const newCheckpoint = currentCheckpoint + 1;

      // Check if this was the final checkpoint (finish line)
      const isFinished = newCheckpoint >= gameState.track.checkpoints.length;
      const finishTime = isFinished
        ? (Date.now() / 1000) - gameState.raceInfo.startTime
        : null;

      return {
        ...gameState,
        raceInfo: {
          ...gameState.raceInfo,
          currentCheckpoint: newCheckpoint,
          isFinished,
          finishTime
        }
      };
    }
  }

  return gameState;
}
