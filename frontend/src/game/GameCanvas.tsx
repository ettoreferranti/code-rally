/**
 * GameCanvas component - Main game rendering canvas.
 */

import React, { useRef, useEffect, useState } from 'react';
import type { GameState } from './types';
import { Camera, renderTrack, renderCar, clearCanvas } from './renderer';

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
  const [fps, setFps] = useState<number>(0);
  const frameCountRef = useRef<number>(0);
  const lastFpsUpdateRef = useRef<number>(Date.now());

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

      if (gameState) {
        // Update camera to follow first car (player)
        if (gameState.cars.length > 0) {
          const playerCar = gameState.cars[0];
          camera.follow(playerCar.position.x, playerCar.position.y, 0.1);
        }

        // Apply camera transform
        camera.apply(ctx, canvas);

        // Render track
        renderTrack(ctx, gameState.track);

        // Render all cars
        gameState.cars.forEach((car, index) => {
          const color = index === 0 ? '#ff0000' : '#0000ff';
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
