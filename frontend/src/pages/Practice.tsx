import { useState, useEffect, useCallback, useMemo } from 'react';
import { GameCanvas, createMockGameState, useKeyboardInput, useGameLoop } from '../game';
import type { GameState, GameLoopCallbacks } from '../game';
import { RaceHUD } from '../components/RaceHUD';
import { generateTrack } from '../services';

export default function Practice() {
  const [gameState, setGameState] = useState<GameState | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const inputState = useKeyboardInput();

  // Parse seed from URL or generate random
  const urlParams = new URLSearchParams(window.location.search);
  const seedParam = urlParams.get('seed');
  const seed = seedParam ? parseInt(seedParam, 10) : Math.floor(Math.random() * 1000000);

  // Initialize game state once - fetch track from API
  useEffect(() => {
    async function initializeRace() {
      try {
        setLoading(true);
        setError(null);

        // Fetch track from backend API
        const track = await generateTrack({ difficulty: 'medium', seed });

        // Create initial car state at start position
        const car = {
          position: { x: track.start_position[0], y: track.start_position[1] },
          velocity: { x: 0, y: 0 },
          heading: track.start_heading,
          angular_velocity: 0,
          is_drifting: false,
          drift_angle: 0,
          throttle: 0,
          is_off_track: false,
          nitro_charges: 2,  // Default nitro charges
          nitro_active: false,
          nitro_remaining_ticks: 0
        };

        // Create game state
        const initialState: GameState = {
          track,
          cars: [car],
          tick: 0,
          raceInfo: {
            currentCheckpoint: 0,
            totalCheckpoints: track.checkpoints.length,
            isFinished: false,
            finishTime: null,
            startTime: Date.now() / 1000
          }
        };

        setGameState(initialState);
      } catch (err) {
        console.error('Failed to load track:', err);
        setError(err instanceof Error ? err.message : 'Failed to load track');
        // Fallback to mock data
        const initialState = createMockGameState();
        setGameState(initialState);
      } finally {
        setLoading(false);
      }
    }

    initializeRace();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Game loop callback to update state (memoized to prevent loop restarts)
  const callbacks: GameLoopCallbacks = useMemo(() => ({
    onUpdate: (newState: GameState) => {
      setGameState(newState);
    }
  }), []);

  // Run the game loop with physics
  useGameLoop(gameState, inputState, callbacks);

  if (loading) {
    return (
      <div className="p-8">
        <h2 className="text-3xl font-bold mb-4">Practice Mode</h2>
        <div className="mt-8 bg-gray-800 p-4 rounded-lg text-center py-12">
          <p className="text-xl text-gray-400">Loading track from server...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-8">
        <h2 className="text-3xl font-bold mb-4">Practice Mode</h2>
        <div className="mt-8 bg-red-900/20 border border-red-600 p-4 rounded-lg">
          <p className="text-red-400">Error: {error}</p>
          <p className="text-sm text-gray-400 mt-2">Using fallback mock data instead.</p>
        </div>
        <div className="mt-8 bg-gray-800 p-4 rounded-lg relative">
          <GameCanvas gameState={gameState} width={800} height={600} />
          {gameState && <RaceHUD raceInfo={gameState.raceInfo} car={gameState.cars[0]} />}
        </div>
      </div>
    );
  }

  return (
    <div className="p-8">
      <h2 className="text-3xl font-bold mb-4">Practice Mode</h2>
      <div className="mb-4 flex gap-4 items-center flex-wrap">
        <div className="text-gray-300">
          <span className="font-semibold">Track Seed:</span> {seed}
          <button
            onClick={() => navigator.clipboard.writeText(seed.toString())}
            className="ml-2 px-2 py-1 text-xs bg-gray-700 rounded hover:bg-gray-600"
            title="Copy seed to clipboard"
          >
            📋 Copy
          </button>
        </div>
        <button
          onClick={() => window.location.reload()}
          className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
          title="Generate new random track"
        >
          🔄 New Track
        </button>
      </div>
      <p className="text-gray-300 mb-4">
        Practice driving with client-side physics. Each reload generates a new random track! Share the seed to practice on the same track.
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
          <li>Procedurally generated tracks from backend API</li>
          <li>Random track generation - each reload creates a new track!</li>
          <li>Reproducible tracks - use <code>?seed=123</code> in URL to load a specific track</li>
          <li>Containment boundaries (outer walls) with variable distance from track</li>
          <li>Dynamic obstacles (rocks, trees, buildings) in off-road areas</li>
          <li>Elastic collision physics for walls and obstacles</li>
          <li>Point-to-point rally stage (start to finish)</li>
          <li>Checkpoint progress tracking and finish line detection</li>
          <li>Multiple surface types with varying grip (asphalt, wet, gravel, ice)</li>
          <li>Off-track detection with speed and grip penalties</li>
          <li>Arcade-style drift physics with strong lateral friction</li>
          <li>Smooth throttle and turn ramping (no "ticking")</li>
          <li>Smooth camera following player</li>
          <li>60 FPS rendering with fixed timestep physics</li>
          <li>Stage completion timer and HUD</li>
          <li>Nitro boost system (Space bar, 1.5x speed for 2 seconds)</li>
        </ul>
      </div>
    </div>
  );
}
