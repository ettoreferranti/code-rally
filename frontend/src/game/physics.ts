/**
 * Physics engine for CodeRally - TypeScript port of backend physics.
 *
 * Handles car physics simulation including acceleration, braking, turning,
 * drag, momentum, and drift mechanics.
 */

import type { Vector2, CarState, SurfaceType, InputState, Track } from './types';
import { SurfaceType as SurfaceTypeEnum } from './types';
import { isOnTrack, checkBoundaryCollision, checkObstacleCollision } from './trackUtils';

/**
 * Physics constants - synchronized with backend configuration.
 *
 * IMPORTANT: These values MUST match backend/app/config.py PhysicsConfig.
 * Values tuned for responsive arcade-style gameplay.
 *
 * For multiplayer mode, the backend is authoritative and runs physics server-side.
 * For single-player mode, the frontend runs physics locally using these constants.
 *
 * Backend exposes these via GET /config/physics endpoint for runtime synchronization.
 */
const PHYSICS_CONFIG = {
  // Movement (arcade-style, responsive)
  MAX_SPEED: 300.0,  // units/second
  ACCELERATION: 250.0,  // units/second^2
  BRAKE_FORCE: 250.0,  // units/second^2
  DRAG_COEFFICIENT: 0.5,  // Drag when coasting
  THROTTLE_RESPONSE: 20.0,  // How quickly throttle ramps up/down (0-1 per second)

  // Turning
  TURN_RATE: 4.5,  // radians/second
  MIN_TURN_SPEED: 1.0,  // Minimum speed to turn effectively
  TURN_ACCELERATION: 20.0,  // How quickly angular velocity ramps up/down

  // Grip and drift
  GRIP_ASPHALT: 1.0,
  GRIP_WET: 0.7,
  GRIP_GRAVEL: 0.5,
  GRIP_ICE: 0.25,
  DRIFT_THRESHOLD: 0.8,  // Higher threshold = less drifting
  DRIFT_RECOVERY_RATE: 15.0,  // Strong grip to kill lateral momentum

  // Off-track penalties
  OFF_TRACK_SPEED_MULTIPLIER: 0.5,  // Speed reduction when off-track
  OFF_TRACK_GRIP_MULTIPLIER: 0.3,    // Grip reduction when off-track

  // Collision
  COLLISION_ELASTICITY: 0.7,  // Bounce coefficient (0 = no bounce, 1 = perfect bounce)
  CAR_RADIUS: 10,  // Car radius for collision detection
  MIN_COLLISION_SPEED: 5.0,  // Minimum speed to trigger bounce (prevent jitter)

  // Nitro
  DEFAULT_NITRO_CHARGES: 2,  // Starting nitro charges
  DEFAULT_NITRO_DURATION_TICKS: 120,  // 2 seconds at 60 Hz
  NITRO_SPEED_MULTIPLIER: 1.5  // 50% speed boost
};

/**
 * Get grip coefficient for a surface type.
 */
function getGripCoefficient(surface: SurfaceType): number {
  switch (surface) {
    case SurfaceTypeEnum.ASPHALT:
      return PHYSICS_CONFIG.GRIP_ASPHALT;
    case SurfaceTypeEnum.WET:
      return PHYSICS_CONFIG.GRIP_WET;
    case SurfaceTypeEnum.GRAVEL:
      return PHYSICS_CONFIG.GRIP_GRAVEL;
    case SurfaceTypeEnum.ICE:
      return PHYSICS_CONFIG.GRIP_ICE;
    default:
      return PHYSICS_CONFIG.GRIP_ASPHALT;
  }
}

/**
 * Vector2 utility functions.
 */
export const Vector2Utils = {
  add(a: Vector2, b: Vector2): Vector2 {
    return { x: a.x + b.x, y: a.y + b.y };
  },

  subtract(a: Vector2, b: Vector2): Vector2 {
    return { x: a.x - b.x, y: a.y - b.y };
  },

  multiply(v: Vector2, scalar: number): Vector2 {
    return { x: v.x * scalar, y: v.y * scalar };
  },

  magnitude(v: Vector2): number {
    return Math.sqrt(v.x * v.x + v.y * v.y);
  },

  normalize(v: Vector2): Vector2 {
    const mag = this.magnitude(v);
    if (mag === 0) return { x: 0, y: 0 };
    return { x: v.x / mag, y: v.y / mag };
  },

  dot(a: Vector2, b: Vector2): number {
    return a.x * b.x + a.y * b.y;
  },

  rotate(v: Vector2, angle: number): Vector2 {
    const cos = Math.cos(angle);
    const sin = Math.sin(angle);
    return {
      x: v.x * cos - v.y * sin,
      y: v.x * sin + v.y * cos
    };
  }
};

/**
 * Car physics engine.
 */
export class CarPhysics {
  /**
   * Update car state based on input.
   */
  update(state: CarState, input: InputState, surface: SurfaceType, track: Track, dt: number): CarState {
    let newState = { ...state };

    // Check if car is on track
    const trackStatus = isOnTrack(track, newState.position);
    newState.is_off_track = !trackStatus.onTrack;

    // Update nitro state
    newState = this.updateNitro(newState, input.nitro);

    // Update throttle state (smoothly ramp up/down)
    newState = this.updateThrottle(newState, input.accelerate, dt);

    // Apply acceleration based on current throttle
    if (newState.throttle > 0) {
      newState = this.applyAcceleration(newState, dt, newState.is_off_track);
    }

    // Apply braking
    if (input.brake) {
      newState = this.applyBraking(newState, dt);
    }

    // Apply turning (always call to handle smooth deceleration)
    const turnDirection = input.turnRight ? 1 : (input.turnLeft ? -1 : 0);
    newState = this.applyTurning(newState, turnDirection, dt);

    // Apply drag only when not accelerating or braking (coasting)
    if (!input.accelerate && !input.brake) {
      newState = this.applyDrag(newState, dt);
    }

    // Apply grip and drift (with off-track penalty)
    let gripCoeff = getGripCoefficient(surface);
    if (newState.is_off_track) {
      gripCoeff *= PHYSICS_CONFIG.OFF_TRACK_GRIP_MULTIPLIER;
    }
    newState = this.applyGrip(newState, gripCoeff, dt);

    // Update position
    newState = this.updatePosition(newState, dt);

    // Handle boundary collisions
    newState = this.handleBoundaryCollision(newState, track);

    // Handle obstacle collisions
    newState = this.handleObstacleCollision(newState, track);

    return newState;
  }

  private updateNitro(state: CarState, useNitro: boolean): CarState {
    let nitroCharges = state.nitro_charges;
    let nitroActive = state.nitro_active;
    let nitroRemainingTicks = state.nitro_remaining_ticks;

    // Activate nitro if button pressed and we have charges
    if (useNitro && !nitroActive && nitroCharges > 0) {
      nitroActive = true;
      nitroCharges -= 1;
      nitroRemainingTicks = PHYSICS_CONFIG.DEFAULT_NITRO_DURATION_TICKS;
    }

    // Deplete nitro over time
    if (nitroActive) {
      nitroRemainingTicks -= 1;
      if (nitroRemainingTicks <= 0) {
        nitroActive = false;
        nitroRemainingTicks = 0;
      }
    }

    return {
      ...state,
      nitro_charges: nitroCharges,
      nitro_active: nitroActive,
      nitro_remaining_ticks: nitroRemainingTicks
    };
  }

  private updateThrottle(state: CarState, isAccelerating: boolean, dt: number): CarState {
    // Calculate target throttle (1 if accelerating, 0 if not)
    const targetThrottle = isAccelerating ? 1.0 : 0.0;

    // Smoothly ramp throttle toward target
    const throttleChange = PHYSICS_CONFIG.THROTTLE_RESPONSE * dt;
    let newThrottle = state.throttle;

    if (Math.abs(targetThrottle - state.throttle) < throttleChange) {
      // Close enough, just set it
      newThrottle = targetThrottle;
    } else if (targetThrottle > state.throttle) {
      // Ramp up
      newThrottle += throttleChange;
    } else {
      // Ramp down
      newThrottle -= throttleChange;
    }

    return {
      ...state,
      throttle: newThrottle
    };
  }

  private applyAcceleration(state: CarState, dt: number, isOffTrack: boolean): CarState {
    const headingVec = {
      x: Math.cos(state.heading),
      y: Math.sin(state.heading)
    };

    // Apply acceleration based on current throttle level (0-1)
    const acceleration = Vector2Utils.multiply(
      headingVec,
      PHYSICS_CONFIG.ACCELERATION * state.throttle * dt
    );
    let newVelocity = Vector2Utils.add(state.velocity, acceleration);

    // Clamp to max speed (with nitro multiplier if active, reduced if off-track)
    let maxSpeed = PHYSICS_CONFIG.MAX_SPEED;
    if (state.nitro_active) {
      maxSpeed *= PHYSICS_CONFIG.NITRO_SPEED_MULTIPLIER;
    }
    if (isOffTrack) {
      maxSpeed *= PHYSICS_CONFIG.OFF_TRACK_SPEED_MULTIPLIER;
    }

    const speed = Vector2Utils.magnitude(newVelocity);
    if (speed > maxSpeed) {
      newVelocity = Vector2Utils.multiply(
        Vector2Utils.normalize(newVelocity),
        maxSpeed
      );
    }

    return {
      ...state,
      velocity: newVelocity
    };
  }

  private applyBraking(state: CarState, dt: number): CarState {
    if (Vector2Utils.magnitude(state.velocity) === 0) {
      return state;
    }

    const brakeDirection = Vector2Utils.multiply(
      Vector2Utils.normalize(state.velocity),
      -1
    );
    const brakeForce = Vector2Utils.multiply(brakeDirection, PHYSICS_CONFIG.BRAKE_FORCE * dt);
    let newVelocity = Vector2Utils.add(state.velocity, brakeForce);

    // Don't reverse from braking
    if (Vector2Utils.dot(state.velocity, newVelocity) < 0) {
      newVelocity = { x: 0, y: 0 };
    }

    return {
      ...state,
      velocity: newVelocity
    };
  }

  private applyTurning(state: CarState, turnDirection: number, dt: number): CarState {
    const speed = Vector2Utils.magnitude(state.velocity);

    // Turning is less effective at low speeds
    const speedFactor = speed < PHYSICS_CONFIG.MIN_TURN_SPEED
      ? speed / PHYSICS_CONFIG.MIN_TURN_SPEED
      : 1.0;

    // Calculate target turn rate
    const targetTurnRate = PHYSICS_CONFIG.TURN_RATE * turnDirection * speedFactor;

    // Smoothly accelerate angular velocity toward target
    const turnAcceleration = PHYSICS_CONFIG.TURN_ACCELERATION * dt;
    let newAngularVelocity = state.angular_velocity;

    if (Math.abs(targetTurnRate - state.angular_velocity) < turnAcceleration) {
      // Close enough, just set it
      newAngularVelocity = targetTurnRate;
    } else if (targetTurnRate > state.angular_velocity) {
      // Accelerate clockwise
      newAngularVelocity += turnAcceleration;
    } else {
      // Accelerate counter-clockwise
      newAngularVelocity -= turnAcceleration;
    }

    // Update heading with smoothed angular velocity
    let newHeading = state.heading + newAngularVelocity * dt;

    // Normalize to [-π, π]
    newHeading = ((newHeading + Math.PI) % (2 * Math.PI)) - Math.PI;

    return {
      ...state,
      heading: newHeading,
      angular_velocity: newAngularVelocity
    };
  }

  private applyDrag(state: CarState, dt: number): CarState {
    const speed = Vector2Utils.magnitude(state.velocity);

    // Already stopped or very slow
    if (speed < 0.1) {
      return {
        ...state,
        velocity: { x: 0, y: 0 }
      };
    }

    // Drag proportional to velocity squared
    const dragMagnitude = PHYSICS_CONFIG.DRAG_COEFFICIENT * speed * dt;
    const dragForce = Vector2Utils.multiply(
      Vector2Utils.normalize(state.velocity),
      -dragMagnitude
    );
    let newVelocity = Vector2Utils.add(state.velocity, dragForce);

    // Don't reverse from drag
    if (Vector2Utils.dot(state.velocity, newVelocity) < 0) {
      newVelocity = { x: 0, y: 0 };
    }

    return {
      ...state,
      velocity: newVelocity
    };
  }

  private applyGrip(state: CarState, gripCoefficient: number, dt: number): CarState {
    const speed = Vector2Utils.magnitude(state.velocity);
    if (speed < 0.1) {
      return {
        ...state,
        is_drifting: false,
        drift_angle: 0
      };
    }

    // Calculate heading and velocity directions
    const headingVec = { x: Math.cos(state.heading), y: Math.sin(state.heading) };
    const velocityDir = Vector2Utils.normalize(state.velocity);
    const lateralVec = { x: Math.sin(state.heading), y: -Math.cos(state.heading) };

    // Decompose velocity into forward and lateral components
    const forwardSpeed = Vector2Utils.dot(state.velocity, headingVec);
    const lateralSpeed = Vector2Utils.dot(state.velocity, lateralVec);

    // Apply STRONG friction to lateral (sideways) movement
    // Sideways friction is much stronger than forward rolling resistance
    const lateralFriction = gripCoefficient * PHYSICS_CONFIG.DRIFT_RECOVERY_RATE * 100.0 * dt;
    let newLateralSpeed = lateralSpeed;

    if (Math.abs(lateralSpeed) > 0.1) {
      // Apply strong friction in opposite direction of sideways movement
      const frictionDirection = -Math.sign(lateralSpeed);
      const frictionMagnitude = Math.min(lateralFriction, Math.abs(lateralSpeed));
      newLateralSpeed = lateralSpeed + frictionDirection * frictionMagnitude;

      // If friction would reverse direction, just stop
      if (Math.sign(newLateralSpeed) !== Math.sign(lateralSpeed)) {
        newLateralSpeed = 0;
      }
    } else {
      newLateralSpeed = 0;
    }

    // Reconstruct velocity with reduced lateral component
    const newVelocity = Vector2Utils.add(
      Vector2Utils.multiply(headingVec, forwardSpeed),
      Vector2Utils.multiply(lateralVec, newLateralSpeed)
    );

    // Check if drifting (significant lateral velocity)
    const isDrifting = Math.abs(newLateralSpeed) > 5.0;
    const driftAngle = isDrifting
      ? Math.acos(Math.max(-1, Math.min(1, Vector2Utils.dot(headingVec, velocityDir))))
      : 0;

    return {
      ...state,
      velocity: newVelocity,
      is_drifting: isDrifting,
      drift_angle: driftAngle
    };
  }

  private updatePosition(state: CarState, dt: number): CarState {
    const newPosition = Vector2Utils.add(
      state.position,
      Vector2Utils.multiply(state.velocity, dt)
    );

    return {
      ...state,
      position: newPosition
    };
  }

  private handleBoundaryCollision(state: CarState, track: Track): CarState {
    // Check for collision with track boundaries
    const collision = checkBoundaryCollision(track, state.position, PHYSICS_CONFIG.CAR_RADIUS);

    if (!collision.collided || !collision.normal || !collision.penetration) {
      return state;
    }

    // Only apply bounce if car is moving fast enough
    const speed = Vector2Utils.magnitude(state.velocity);
    if (speed < PHYSICS_CONFIG.MIN_COLLISION_SPEED) {
      // Just push car back to valid position
      const pushback = Vector2Utils.multiply(collision.normal, collision.penetration);
      return {
        ...state,
        position: Vector2Utils.add(state.position, pushback),
        velocity: Vector2Utils.multiply(state.velocity, 0.5)  // Dampen velocity
      };
    }

    // Calculate reflection using elastic collision formula
    // v' = v - (1 + e) * (v · n) * n
    // where e is elasticity coefficient, n is collision normal

    const velocityDotNormal = Vector2Utils.dot(state.velocity, collision.normal);

    // Only bounce if moving into the wall (not away from it)
    if (velocityDotNormal >= 0) {
      return state;  // Already moving away from wall
    }

    // Apply elastic bounce
    const bounce = Vector2Utils.multiply(
      collision.normal,
      -(1 + PHYSICS_CONFIG.COLLISION_ELASTICITY) * velocityDotNormal
    );

    const newVelocity = Vector2Utils.add(state.velocity, bounce);

    // Push car back out of the boundary
    const pushback = Vector2Utils.multiply(collision.normal, collision.penetration);
    const newPosition = Vector2Utils.add(state.position, pushback);

    return {
      ...state,
      position: newPosition,
      velocity: newVelocity
    };
  }

  private handleObstacleCollision(state: CarState, track: Track): CarState {
    // Check for collision with obstacles
    const collision = checkObstacleCollision(track, state.position, PHYSICS_CONFIG.CAR_RADIUS);

    if (!collision.collided || !collision.normal || !collision.penetration) {
      return state;
    }

    // Only apply bounce if car is moving fast enough
    const speed = Vector2Utils.magnitude(state.velocity);
    if (speed < PHYSICS_CONFIG.MIN_COLLISION_SPEED) {
      // Just push car back to valid position
      const pushback = Vector2Utils.multiply(collision.normal, collision.penetration);
      return {
        ...state,
        position: Vector2Utils.add(state.position, pushback),
        velocity: Vector2Utils.multiply(state.velocity, 0.5)  // Dampen velocity
      };
    }

    // Calculate reflection using elastic collision formula
    const velocityDotNormal = Vector2Utils.dot(state.velocity, collision.normal);

    // Only bounce if moving into the obstacle (not away from it)
    if (velocityDotNormal >= 0) {
      return state;  // Already moving away from obstacle
    }

    // Apply elastic bounce
    const bounce = Vector2Utils.multiply(
      collision.normal,
      -(1 + PHYSICS_CONFIG.COLLISION_ELASTICITY) * velocityDotNormal
    );

    const newVelocity = Vector2Utils.add(state.velocity, bounce);

    // Push car back out of the obstacle
    const pushback = Vector2Utils.multiply(collision.normal, collision.penetration);
    const newPosition = Vector2Utils.add(state.position, pushback);

    return {
      ...state,
      position: newPosition,
      velocity: newVelocity
    };
  }
}
