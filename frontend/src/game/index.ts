// Game rendering and loop exports
export { GameCanvas } from './GameCanvas';
export { Camera, renderTrack, renderCar, clearCanvas } from './renderer';
export { createMockGameState, updateMockCar } from './mockData';
export { useKeyboardInput } from './useKeyboardInput';

// Export types and enums
export { SurfaceType } from './types';
export type { GameState, CarState, Track, TrackSegment, Checkpoint, Vector2, TrackPoint, InputState } from './types';
