import { useState, useEffect } from 'react';
import { GameCanvas, createMockGameState, updateMockCar, useKeyboardInput } from '../game';
import type { GameState } from '../game';

export default function Race() {
  const [gameState, setGameState] = useState<GameState | null>(null);
  const inputState = useKeyboardInput();

  useEffect(() => {
    // Initialize mock game state
    const initialState = createMockGameState();
    setGameState(initialState);

    // Animate the car moving around the track
    const interval = setInterval(() => {
      setGameState((prevState) => {
        if (!prevState) return prevState;
        return updateMockCar(prevState, 0.05); // 50ms delta time
      });
    }, 50);

    return () => clearInterval(interval);
  }, []);

  return (
    <div className="p-8">
      <h2 className="text-3xl font-bold mb-4">Race</h2>
      <p className="text-gray-300 mb-4">
        Live demonstration of game rendering with a car moving around a procedurally generated track
      </p>
      <div className="mt-8 bg-gray-800 p-4 rounded-lg">
        <GameCanvas gameState={gameState} width={800} height={600} />
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
          <li>Track rendering with bezier curves</li>
          <li>Multiple surface types (asphalt, wet, gravel, ice)</li>
          <li>Car rendering with heading indicator</li>
          <li>Smooth camera following</li>
          <li>60 FPS rendering (check FPS counter)</li>
          <li>Checkpoints visualization</li>
          <li>Keyboard input handling with simultaneous key presses</li>
        </ul>
      </div>
    </div>
  );
}
