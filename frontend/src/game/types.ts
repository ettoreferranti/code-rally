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

export interface ContainmentBoundary {
  left_points: [number, number][];
  right_points: [number, number][];
}

export interface Obstacle {
  position: [number, number];
  radius: number;
  type: string;  // 'rock', 'tree', 'building'
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
  containment?: ContainmentBoundary;  // Outer collision walls
  obstacles: Obstacle[];  // Off-road obstacles
}

export interface CarState {
  position: Vector2;
  velocity: Vector2;
  heading: number;
  angular_velocity: number;
  is_drifting: boolean;
  drift_angle: number;
  throttle: number;  // Current throttle level (0-1) for smooth acceleration
  is_off_track: boolean;  // Whether car is currently off-track
  nitro_charges: number;  // Number of nitro boosts remaining
  nitro_active: boolean;  // Whether nitro is currently active
  nitro_remaining_ticks: number;  // Ticks remaining for current nitro boost
}

export interface RaceInfo {
  currentCheckpoint: number;  // Next checkpoint index to pass
  totalCheckpoints: number;
  isFinished: boolean;
  finishTime: number | null;  // Time in seconds when finished
  startTime: number | null;  // Time in seconds when race started
  countdownRemaining?: number;  // Countdown seconds remaining before race starts
  raceStatus?: string;  // Race status: 'waiting', 'countdown', 'racing', 'finished'
  firstFinisherTime?: number | null;  // Time when first player finished (for grace period)
  gracePeriodRemaining?: number;  // Seconds remaining for other players to finish
  currentPosition?: number | null;  // Current race position (1st, 2nd, etc.)
  totalPlayers?: number;  // Total number of players in the race
}

/**
 * Race result for a single player.
 */
export interface PlayerResult {
  playerId: string;
  playerName?: string;
  position: number | null;  // Final position (1st, 2nd, 3rd, etc.) - null for DNF
  finishTime: number | null;  // Total stage time in seconds
  points: number;  // Points awarded based on position
  dnf: boolean;  // Did Not Finish
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
