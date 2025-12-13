/**
 * Physics engine for CodeRally - TypeScript port of backend physics.
 *
 * Handles car physics simulation including acceleration, braking, turning,
 * drag, momentum, and drift mechanics.
 */

import type { Vector2, CarState, SurfaceType, InputState } from './types';
import { SurfaceType as SurfaceTypeEnum } from './types';

/**
 * Physics constants - tuned for responsive arcade-style controls.
 */
const PHYSICS_CONFIG = {
  // Movement
  MAX_SPEED: 300.0,  // units/second (50% increase for more speed!)
  ACCELERATION: 250.0,  // units/second^2 (increased for faster acceleration)
  BRAKE_FORCE: 250.0,  // units/second^2 (increased to match higher speeds)
  DRAG_COEFFICIENT: 0.5,  // Increased to slow down when not accelerating
  THROTTLE_RESPONSE: 20.0,  // How quickly throttle ramps up/down (0-1 per second)

  // Turning
  TURN_RATE: 4.5,  // radians/second (increased by 50% for better turning)
  MIN_TURN_SPEED: 1.0,  // Reduced so you can turn at lower speeds
  TURN_ACCELERATION: 20.0,  // How quickly angular velocity ramps up/down

  // Grip and drift
  GRIP_ASPHALT: 1.0,
  GRIP_WET: 0.7,
  GRIP_GRAVEL: 0.5,
  GRIP_ICE: 0.25,
  DRIFT_THRESHOLD: 0.8,  // Higher threshold = less drifting
  DRIFT_RECOVERY_RATE: 15.0  // Much stronger grip to kill lateral momentum faster
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
  update(state: CarState, input: InputState, surface: SurfaceType, dt: number): CarState {
    let newState = { ...state };

    // Update throttle state (smoothly ramp up/down)
    newState = this.updateThrottle(newState, input.accelerate, dt);

    // Apply acceleration based on current throttle
    if (newState.throttle > 0) {
      newState = this.applyAcceleration(newState, dt);
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

    // Apply grip and drift
    const gripCoeff = getGripCoefficient(surface);
    newState = this.applyGrip(newState, gripCoeff, dt);

    // Update position
    newState = this.updatePosition(newState, dt);

    return newState;
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

  private applyAcceleration(state: CarState, dt: number): CarState {
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

    // Clamp to max speed
    const speed = Vector2Utils.magnitude(newVelocity);
    if (speed > PHYSICS_CONFIG.MAX_SPEED) {
      newVelocity = Vector2Utils.multiply(
        Vector2Utils.normalize(newVelocity),
        PHYSICS_CONFIG.MAX_SPEED
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
}
