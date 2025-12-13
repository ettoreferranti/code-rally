// Game rendering and loop exports
export { GameCanvas } from './GameCanvas';
export { Camera, renderTrack, renderCar, clearCanvas } from './renderer';
export { createMockGameState, updateMockCar } from './mockData';
export { useKeyboardInput } from './useKeyboardInput';
export { useGameLoop } from './useGameLoop';
export type { GameLoopCallbacks } from './useGameLoop';
export { CarPhysics, Vector2Utils } from './physics';
export { getSurfaceAtPosition, isOnTrack, checkBoundaryCollision, checkObstacleCollision } from './trackUtils';
export type { CollisionResult, BoundaryEdge } from './trackUtils';
export { updateCheckpointProgress } from './checkpointUtils';

// Export types and enums
export { SurfaceType } from './types';
export type { GameState, CarState, Track, TrackSegment, Checkpoint, Vector2, TrackPoint, InputState, RaceInfo, ContainmentBoundary, Obstacle } from './types';
