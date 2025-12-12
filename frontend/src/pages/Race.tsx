import { useState, useEffect } from 'react';
import { GameCanvas, createMockGameState, updateMockCar } from '../game';
import type { GameState } from '../game';

export default function Race() {
  const [gameState, setGameState] = useState<GameState | null>(null);

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
      <div className="mt-4 text-sm text-gray-400">
        <p>Features demonstrated:</p>
        <ul className="list-disc list-inside ml-4 mt-2">
          <li>Track rendering with bezier curves</li>
          <li>Multiple surface types (asphalt, wet, gravel, ice)</li>
          <li>Car rendering with heading indicator</li>
          <li>Smooth camera following</li>
          <li>60 FPS rendering (check FPS counter)</li>
          <li>Checkpoints visualization</li>
        </ul>
      </div>
    </div>
  );
}
