/**
 * State buffer for smooth interpolation between server updates.
 *
 * This module provides client-side interpolation to smooth out visual stuttering
 * caused by timing mismatches between server updates (60Hz) and client rendering (60 FPS).
 */

import type { GameState, CarState } from './types';

interface BufferedState {
  timestamp: number;  // Client timestamp when received
  serverTick: number; // Server tick number
  state: GameState;
}

export class StateBuffer {
  private states: BufferedState[] = [];
  private maxBufferSize = 3;  // Keep last 3 states
  private renderDelay = 100;  // ms - render 100ms behind latest

  /**
   * Add new state to buffer.
   * @param state Game state from server
   * @param clientTimestamp Client timestamp when received (use performance.now())
   */
  addState(state: GameState, clientTimestamp: number): void {
    this.states.push({
      timestamp: clientTimestamp,
      serverTick: state.tick,
      state: state
    });

    // Keep buffer size limited
    if (this.states.length > this.maxBufferSize) {
      this.states.shift();  // Remove oldest
    }

    // Sort by timestamp (handle out-of-order packets)
    this.states.sort((a, b) => a.timestamp - b.timestamp);
  }

  /**
   * Get interpolated state for current render time.
   * @param currentTime Current time from performance.now()
   * @returns Interpolated game state or null if no states available
   */
  getInterpolatedState(currentTime: number): GameState | null {
    if (this.states.length < 2) {
      // Not enough states to interpolate - return latest or null
      return this.states.length > 0 ? this.states[0].state : null;
    }

    // Calculate render time (slightly behind current time)
    const renderTime = currentTime - this.renderDelay;

    // Find two states to interpolate between
    let olderState: BufferedState | null = null;
    let newerState: BufferedState | null = null;

    for (let i = 0; i < this.states.length - 1; i++) {
      if (this.states[i].timestamp <= renderTime &&
          this.states[i + 1].timestamp >= renderTime) {
        olderState = this.states[i];
        newerState = this.states[i + 1];
        break;
      }
    }

    // Edge case: renderTime before first state (extrapolate backward - not recommended)
    if (!olderState && this.states.length >= 1) {
      return this.states[0].state;  // Use oldest available
    }

    // Edge case: renderTime after last state (extrapolate forward briefly)
    if (!newerState && this.states.length >= 1) {
      const latestState = this.states[this.states.length - 1];
      const timeSinceLatest = renderTime - latestState.timestamp;

      // Only extrapolate up to 100ms
      if (timeSinceLatest < 100) {
        return this.extrapolateState(latestState.state, timeSinceLatest);
      }

      // Too old - just use latest
      return latestState.state;
    }

    // Normal case: interpolate between two states
    if (olderState && newerState) {
      const timeDelta = newerState.timestamp - olderState.timestamp;
      const alpha = (renderTime - olderState.timestamp) / timeDelta;

      // Clamp alpha to [0, 1]
      const clampedAlpha = Math.max(0, Math.min(1, alpha));

      return this.interpolateStates(olderState.state, newerState.state, clampedAlpha);
    }

    // Fallback
    return this.states[this.states.length - 1].state;
  }

  /**
   * Interpolate between two game states.
   * @param oldState Older game state
   * @param newState Newer game state
   * @param alpha Interpolation factor [0, 1]
   * @returns Interpolated game state
   */
  private interpolateStates(oldState: GameState, newState: GameState, alpha: number): GameState {
    // Interpolate each car
    const interpolatedCars = newState.cars.map((newCar, index) => {
      // Find matching car in old state (by playerId if available, otherwise by index)
      const oldCar = newCar.playerId
        ? oldState.cars.find(c => c.playerId === newCar.playerId)
        : oldState.cars[index];

      // If car doesn't exist in old state, use new state directly
      if (!oldCar) return newCar;

      return this.interpolateCar(oldCar, newCar, alpha);
    });

    // Return interpolated game state
    return {
      ...newState,  // Keep all non-car data from new state
      cars: interpolatedCars
    };
  }

  /**
   * Interpolate between two car states.
   * @param oldCar Older car state
   * @param newCar Newer car state
   * @param alpha Interpolation factor [0, 1]
   * @returns Interpolated car state
   */
  private interpolateCar(oldCar: CarState, newCar: CarState, alpha: number): CarState {
    return {
      ...newCar,  // Keep all properties from new state
      // Interpolate position
      position: {
        x: this.lerp(oldCar.position.x, newCar.position.x, alpha),
        y: this.lerp(oldCar.position.y, newCar.position.y, alpha)
      },
      // Interpolate heading (angle)
      heading: this.lerpAngle(oldCar.heading, newCar.heading, alpha),
      // Interpolate velocity (optional - for smoother feel)
      velocity: {
        x: this.lerp(oldCar.velocity.x, newCar.velocity.x, alpha),
        y: this.lerp(oldCar.velocity.y, newCar.velocity.y, alpha)
      },
      // Interpolate angular velocity
      angular_velocity: this.lerp(oldCar.angular_velocity, newCar.angular_velocity, alpha),
      // Interpolate drift angle
      drift_angle: this.lerpAngle(oldCar.drift_angle, newCar.drift_angle, alpha)
    };
  }

  /**
   * Extrapolate state forward using velocity.
   * @param state Current game state
   * @param deltaMs Time to extrapolate forward in milliseconds
   * @returns Extrapolated game state
   */
  private extrapolateState(state: GameState, deltaMs: number): GameState {
    const deltaSec = deltaMs / 1000.0;

    const extrapolatedCars = state.cars.map(car => ({
      ...car,
      position: {
        x: car.position.x + car.velocity.x * deltaSec,
        y: car.position.y + car.velocity.y * deltaSec
      }
      // Don't extrapolate heading - too unpredictable with steering
    }));

    return {
      ...state,
      cars: extrapolatedCars
    };
  }

  /**
   * Linear interpolation between two numbers.
   * @param a Start value
   * @param b End value
   * @param t Interpolation factor [0, 1]
   * @returns Interpolated value
   */
  private lerp(a: number, b: number, t: number): number {
    return a + (b - a) * t;
  }

  /**
   * Interpolate between two angles (handles wrap-around).
   * @param a Start angle in radians
   * @param b End angle in radians
   * @param t Interpolation factor [0, 1]
   * @returns Interpolated angle in radians
   */
  private lerpAngle(a: number, b: number, t: number): number {
    // Normalize angles to [0, 2π]
    a = ((a % (2 * Math.PI)) + (2 * Math.PI)) % (2 * Math.PI);
    b = ((b % (2 * Math.PI)) + (2 * Math.PI)) % (2 * Math.PI);

    // Calculate shortest path
    let diff = b - a;
    if (diff > Math.PI) {
      diff -= 2 * Math.PI;
    } else if (diff < -Math.PI) {
      diff += 2 * Math.PI;
    }

    return a + diff * t;
  }

  /**
   * Clear buffer (on disconnect/reset).
   */
  clear(): void {
    this.states = [];
  }

  /**
   * Get buffer size (for debugging).
   * @returns Number of states currently in buffer
   */
  getBufferSize(): number {
    return this.states.length;
  }
}
