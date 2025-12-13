import { useState, useEffect, useCallback } from 'react';
import { GameCanvas, createMockGameState, useKeyboardInput, useGameLoop } from '../game';
import type { GameState, GameLoopCallbacks } from '../game';
import { RaceHUD } from '../components/RaceHUD';

export default function Race() {
  const [gameState, setGameState] = useState<GameState | null>(null);
  const inputState = useKeyboardInput();

  // Initialize game state once
  useEffect(() => {
    const initialState = createMockGameState();
    setGameState(initialState);
  }, []);

  // Game loop callback to update state
  const callbacks: GameLoopCallbacks = useCallback({
    onUpdate: (newState: GameState) => {
      setGameState(newState);
    }
  }, []);

  // Run the game loop with physics
  useGameLoop(gameState, inputState, callbacks);

  return (
    <div className="p-8">
      <h2 className="text-3xl font-bold mb-4">Rally Stage</h2>
      <p className="text-gray-300 mb-4">
        Drive through the point-to-point rally stage and reach the finish line as fast as you can!
      </p>
      <div className="mt-8 bg-gray-800 p-4 rounded-lg relative">
        <GameCanvas gameState={gameState} width={800} height={600} />
        {gameState && <RaceHUD raceInfo={gameState.raceInfo} car={gameState.cars[0]} />}
      </div>

      {/* Keyboard Input Display */}
      <div className="mt-4 bg-gray-800 p-4 rounded-lg">
        <h3 className="text-lg font-semibold mb-3">Keyboard Controls</h3>
        <p className="text-sm text-gray-400 mb-3">
          Press keys to test input handling (WASD or Arrow Keys, Space for Nitro)
        </p>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          <div className={`p-3 rounded text-center transition-colors ${
            inputState.accelerate ? 'bg-green-600' : 'bg-gray-700'
          }`}>
            <div className="font-semibold">Accelerate</div>
            <div className="text-sm text-gray-300">W / ↑</div>
          </div>
          <div className={`p-3 rounded text-center transition-colors ${
            inputState.brake ? 'bg-red-600' : 'bg-gray-700'
          }`}>
            <div className="font-semibold">Brake</div>
            <div className="text-sm text-gray-300">S / ↓</div>
          </div>
          <div className={`p-3 rounded text-center transition-colors ${
            inputState.turnLeft ? 'bg-blue-600' : 'bg-gray-700'
          }`}>
            <div className="font-semibold">Turn Left</div>
            <div className="text-sm text-gray-300">A / ←</div>
          </div>
          <div className={`p-3 rounded text-center transition-colors ${
            inputState.turnRight ? 'bg-blue-600' : 'bg-gray-700'
          }`}>
            <div className="font-semibold">Turn Right</div>
            <div className="text-sm text-gray-300">D / →</div>
          </div>
          <div className={`p-3 rounded text-center transition-colors ${
            inputState.nitro ? 'bg-purple-600' : 'bg-gray-700'
          }`}>
            <div className="font-semibold">Nitro</div>
            <div className="text-sm text-gray-300">Space</div>
          </div>
        </div>
      </div>

      <div className="mt-4 text-sm text-gray-400">
        <p>Features demonstrated:</p>
        <ul className="list-disc list-inside ml-4 mt-2">
          <li>Real-time physics simulation at 60Hz</li>
          <li>Point-to-point rally stage (start to finish)</li>
          <li>Checkpoint progress tracking and finish line detection</li>
          <li>Multiple surface types with varying grip (asphalt, wet, gravel, ice)</li>
          <li>Arcade-style drift physics with strong lateral friction</li>
          <li>Smooth throttle and turn ramping (no "ticking")</li>
          <li>Smooth camera following player</li>
          <li>60 FPS rendering with fixed timestep physics</li>
          <li>Stage completion timer and HUD</li>
        </ul>
      </div>
    </div>
  );
}
