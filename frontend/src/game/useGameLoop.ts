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
  const inputStateRef = useRef(inputState);
  const callbacksRef = useRef(callbacks);
  const currentGameStateRef = useRef<GameState | null>(null);
  const hasStartedRef = useRef(false);

  // Update refs when values change (without restarting the loop)
  useEffect(() => {
    inputStateRef.current = inputState;
  }, [inputState]);

  useEffect(() => {
    callbacksRef.current = callbacks;
  }, [callbacks]);

  // Separate effect to update game state ref (doesn't restart loop)
  useEffect(() => {
    if (gameState && !currentGameStateRef.current) {
      currentGameStateRef.current = gameState;
    }
  }, [gameState]);

  // Start the game loop once (only runs once on mount)
  useEffect(() => {
    // Wait for game state to be ready
    const waitForGameState = setInterval(() => {
      if (currentGameStateRef.current && !hasStartedRef.current) {
        clearInterval(waitForGameState);
        hasStartedRef.current = true;
        startLoop();
      }
    }, 10);

    const startLoop = () => {
      const physics = physicsRef.current;
      let running = true;
      let animationFrameId: number;

      // Initialize previous car position
      const initialState = currentGameStateRef.current!;
      if (initialState.cars.length > 0) {
        prevCarPosRef.current = { ...initialState.cars[0].position };
      }

      const gameLoop = (currentTime: number) => {
        if (!running || !currentGameStateRef.current) {
          return;
        }

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
          const currentState = currentGameStateRef.current;

          // Store previous car position for checkpoint detection
          const prevCarPos = prevCarPosRef.current || currentState.cars[0]?.position || { x: 0, y: 0 };

          // Update physics for each car
          const updatedCars = currentState.cars.map((car, index) => {
            // Detect surface type at car's position
            const surface = getSurfaceAtPosition(currentState.track, car.position);

            // Only apply input to first car (player)
            const carInput = index === 0 ? inputStateRef.current : {
              accelerate: false,
              brake: false,
              turnLeft: false,
              turnRight: false,
              nitro: false
            };

            return physics.update(car, carInput, surface, currentState.track, PHYSICS_DT);
          });

          // Create new game state with updated cars
          const newState: GameState = {
            ...currentState,
            cars: updatedCars,
            tick: currentState.tick + 1
          };

          // Check for checkpoint progress
          currentGameStateRef.current = updateCheckpointProgress(newState, prevCarPos);

          // Update previous car position
          if (currentGameStateRef.current.cars.length > 0) {
            prevCarPosRef.current = { ...currentGameStateRef.current.cars[0].position };
          }

          accumulatorRef.current -= PHYSICS_DT;
        }

        // Notify of updated state
        callbacksRef.current.onUpdate(currentGameStateRef.current);

        // Continue loop
        animationFrameId = requestAnimationFrame(gameLoop);
      };

      // Start the loop
      animationFrameId = requestAnimationFrame(gameLoop);
    };

    // Cleanup function (only on unmount)
    return () => {
      clearInterval(waitForGameState);
    };
  }, []); // Empty deps - only run once on mount, cleanup on unmount
}
