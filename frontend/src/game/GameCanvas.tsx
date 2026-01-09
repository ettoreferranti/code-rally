/**
 * GameCanvas component - Main game rendering canvas.
 */

import React, { useRef, useEffect, useState } from 'react';
import type { GameState } from './types';
import { Camera, renderTrack, renderCar, clearCanvas } from './renderer';
import { StateBuffer } from './StateInterpolation';

interface GameCanvasProps {
  gameState: GameState | null;
  width?: number;
  height?: number;
}

export const GameCanvas: React.FC<GameCanvasProps> = ({
  gameState,
  width = 800,
  height = 600
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const cameraRef = useRef<Camera>(new Camera());
  const stateBufferRef = useRef<StateBuffer>(new StateBuffer());
  const [fps, setFps] = useState<number>(0);
  const frameCountRef = useRef<number>(0);
  const lastFpsUpdateRef = useRef<number>(Date.now());

  // Buffer incoming game states for interpolation
  useEffect(() => {
    if (gameState) {
      stateBufferRef.current.addState(gameState, performance.now());
    }
  }, [gameState]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const camera = cameraRef.current;

    // Set canvas size
    canvas.width = width;
    canvas.height = height;

    // Render loop
    let animationFrameId: number;
    let lastFrameTime = performance.now();

    const render = (currentTime: number) => {
      const deltaTime = currentTime - lastFrameTime;
      lastFrameTime = currentTime;

      // FPS counter
      frameCountRef.current++;
      const now = Date.now();
      if (now - lastFpsUpdateRef.current >= 1000) {
        setFps(frameCountRef.current);
        frameCountRef.current = 0;
        lastFpsUpdateRef.current = now;
      }

      // Clear canvas
      clearCanvas(ctx, canvas);

      // Get interpolated state for smooth rendering
      const interpolatedState = stateBufferRef.current.getInterpolatedState(currentTime);

      if (interpolatedState) {
        // Update camera to follow current player's car
        if (interpolatedState.cars.length > 0) {
          const playerCar = interpolatedState.cars.find(car => car.isCurrentPlayer) || interpolatedState.cars[0];
          camera.follow(playerCar.position.x, playerCar.position.y, 0.1);
        }

        // Apply camera transform
        camera.apply(ctx, canvas);

        // Render track
        renderTrack(ctx, interpolatedState.track);

        // Render all cars with interpolated positions
        interpolatedState.cars.forEach((car) => {
          // Current player is red, other humans are blue, bots are yellow
          let color = '#0000ff'; // Other players (blue)
          if (car.isCurrentPlayer) {
            color = '#ff0000'; // Current player (red)
          } else if (car.isBot) {
            color = '#ffff00'; // Bots (yellow)
          }
          renderCar(ctx, car, color);
        });
      } else {
        // No game state - show placeholder
        ctx.setTransform(1, 0, 0, 1, 0, 0);
        ctx.fillStyle = '#ffffff';
        ctx.font = '24px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('Waiting for game state...', canvas.width / 2, canvas.height / 2);
      }

      // Continue render loop
      animationFrameId = requestAnimationFrame(render);
    };

    // Start render loop
    animationFrameId = requestAnimationFrame(render);

    // Cleanup
    return () => {
      cancelAnimationFrame(animationFrameId);
      stateBufferRef.current.clear(); // Clear buffer on unmount
    };
  }, [gameState, width, height]);

  return (
    <div className="relative">
      <canvas
        ref={canvasRef}
        className="border border-gray-700 rounded"
        style={{ display: 'block' }}
      />
      <div className="absolute top-2 right-2 bg-black bg-opacity-50 text-white px-3 py-1 rounded text-sm">
        FPS: {fps}
      </div>
    </div>
  );
};

export default GameCanvas;
