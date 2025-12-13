/**
 * Game state types for CodeRally frontend.
 */

export enum SurfaceType {
  ASPHALT = "asphalt",
  WET = "wet",
  GRAVEL = "gravel",
  ICE = "ice"
}

export interface Vector2 {
  x: number;
  y: number;
}

export interface TrackPoint {
  x: number;
  y: number;
  width: number;
  surface: SurfaceType;
}

export interface TrackSegment {
  start: TrackPoint;
  end: TrackPoint;
  control1?: [number, number];
  control2?: [number, number];
}

export interface Checkpoint {
  position: [number, number];
  angle: number;
  width: number;
  index: number;
}

export interface Track {
  segments: TrackSegment[];
  checkpoints: Checkpoint[];
  start_position: [number, number];
  start_heading: number;
  finish_position: [number, number];
  finish_heading: number;
  total_length: number;
  is_looping: boolean;  // false for rally stages, true for circuits
}

export interface CarState {
  position: Vector2;
  velocity: Vector2;
  heading: number;
  angular_velocity: number;
  is_drifting: boolean;
  drift_angle: number;
  throttle: number;  // Current throttle level (0-1) for smooth acceleration
}

export interface RaceInfo {
  currentCheckpoint: number;  // Next checkpoint index to pass
  totalCheckpoints: number;
  isFinished: boolean;
  finishTime: number | null;  // Time in seconds when finished
  startTime: number;  // Time in seconds when race started
}

export interface GameState {
  track: Track;
  cars: CarState[];
  tick: number;
  raceInfo: RaceInfo;
}

/**
 * Input actions for controlling a car.
 */
export interface InputState {
  accelerate: boolean;
  brake: boolean;
  turnLeft: boolean;
  turnRight: boolean;
  nitro: boolean;
}
