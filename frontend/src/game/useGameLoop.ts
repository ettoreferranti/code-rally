/**
 * Game loop hook with fixed 60Hz physics updates.
 */

import { useEffect, useRef } from 'react';
import type { GameState, InputState, Vector2 } from './types';
import { CarPhysics } from './physics';
import { getSurfaceAtPosition } from './trackUtils';
import { updateCheckpointProgress } from './checkpointUtils';

const PHYSICS_TICK_RATE = 60; // Hz
const PHYSICS_DT = 1 / PHYSICS_TICK_RATE; // seconds per tick

export interface GameLoopCallbacks {
  onUpdate: (gameState: GameState) => void;
}

/**
 * Hook to run the game loop with fixed 60Hz physics updates.
 *
 * @param gameState Current game state
 * @param inputState Current input state
 * @param callbacks Callbacks for game updates
 */
export function useGameLoop(
  gameState: GameState | null,
  inputState: InputState,
  callbacks: GameLoopCallbacks
): void {
  const physicsRef = useRef(new CarPhysics());
  const lastTickRef = useRef(0);
  const accumulatorRef = useRef(0);
  const prevCarPosRef = useRef<Vector2 | null>(null);

  useEffect(() => {
    if (!gameState) return;

    const physics = physicsRef.current;
    let animationFrameId: number;
    let running = true;
    let currentGameState = gameState;

    // Initialize previous car position
    if (gameState.cars.length > 0) {
      prevCarPosRef.current = { ...gameState.cars[0].position };
    }

    const gameLoop = (currentTime: number) => {
      if (!running) return;

      // Initialize lastTick on first frame
      if (lastTickRef.current === 0) {
        lastTickRef.current = currentTime;
      }

      // Calculate frame delta time (in seconds)
      const frameDelta = (currentTime - lastTickRef.current) / 1000;
      lastTickRef.current = currentTime;

      // Accumulate time
      accumulatorRef.current += frameDelta;

      // Cap accumulator to prevent spiral of death
      if (accumulatorRef.current > 0.25) {
        accumulatorRef.current = 0.25;
      }

      // Run physics updates at fixed timestep
      while (accumulatorRef.current >= PHYSICS_DT) {
        // Store previous car position for checkpoint detection
        const prevCarPos = prevCarPosRef.current || currentGameState.cars[0]?.position || { x: 0, y: 0 };

        // Update physics for each car
        const updatedCars = currentGameState.cars.map((car, index) => {
          // Detect surface type at car's position
          const surface = getSurfaceAtPosition(currentGameState.track, car.position);

          // Only apply input to first car (player)
          const carInput = index === 0 ? inputState : {
            accelerate: false,
            brake: false,
            turnLeft: false,
            turnRight: false,
            nitro: false
          };

          return physics.update(car, carInput, surface, currentGameState.track, PHYSICS_DT);
        });

        // Create new game state with updated cars
        currentGameState = {
          ...currentGameState,
          cars: updatedCars,
          tick: currentGameState.tick + 1
        };

        // Check for checkpoint progress
        currentGameState = updateCheckpointProgress(currentGameState, prevCarPos);

        // Update previous car position
        if (currentGameState.cars.length > 0) {
          prevCarPosRef.current = { ...currentGameState.cars[0].position };
        }

        accumulatorRef.current -= PHYSICS_DT;
      }

      // Notify of updated state
      callbacks.onUpdate(currentGameState);

      // Continue loop
      animationFrameId = requestAnimationFrame(gameLoop);
    };

    // Start the loop
    animationFrameId = requestAnimationFrame(gameLoop);

    // Cleanup
    return () => {
      running = false;
      cancelAnimationFrame(animationFrameId);
      lastTickRef.current = 0;
      accumulatorRef.current = 0;
    };
  }, [gameState, inputState, callbacks]);
}
