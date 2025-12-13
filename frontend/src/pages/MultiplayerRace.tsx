import { useState, useEffect, useRef } from 'react';
import { GameCanvas, useKeyboardInput } from '../game';
import type { GameState, Track } from '../game/types';
import { RaceHUD } from '../components/RaceHUD';
import { GameWebSocketClient, type GameStateMessage } from '../services';

export default function MultiplayerRace() {
  const [track, setTrack] = useState<Track | null>(null);
  const [gameState, setGameState] = useState<GameState | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [playerId, setPlayerId] = useState<string | null>(null);
  const [raceStarted, setRaceStarted] = useState(false);

  const inputState = useKeyboardInput();
  const wsRef = useRef<GameWebSocketClient | null>(null);
  const inputIntervalRef = useRef<number | null>(null);

  // Initialize WebSocket connection
  useEffect(() => {
    const ws = new GameWebSocketClient({
      onConnected: (sid, pid, receivedTrack) => {
        console.log('Connected to game session:', sid);
        setSessionId(sid);
        setPlayerId(pid);
        setTrack(receivedTrack);
        setLoading(false);
      },

      onGameState: (state: GameStateMessage['data']) => {
        // Convert server state to frontend GameState format
        if (!track || !playerId) return;

        const playerData = state.players[playerId];
        if (!playerData) return;

        const newGameState: GameState = {
          track,
          cars: [{
            position: playerData.car.position,
            velocity: playerData.car.velocity,
            heading: playerData.car.heading,
            angular_velocity: playerData.car.angular_velocity,
            is_drifting: playerData.car.is_drifting,
            drift_angle: playerData.car.drift_angle,
            throttle: 0,  // Not tracked server-side yet
            is_off_track: playerData.is_off_track,
          }],
          tick: state.tick,
          raceInfo: {
            currentCheckpoint: playerData.current_checkpoint,
            totalCheckpoints: track.checkpoints.length,
            isFinished: playerData.is_finished,
            finishTime: playerData.finish_time,
            startTime: state.race_info.start_time,
            countdownRemaining: state.race_info.countdown_remaining,
          }
        };

        setGameState(newGameState);
      },

      onDisconnected: () => {
        console.log('Disconnected from game session');
        setError('Disconnected from server');
      },

      onError: (event) => {
        console.error('WebSocket error:', event);
        setError('Connection error');
      },
    });

    wsRef.current = ws;
    ws.connect(undefined, 'medium', 42);  // Connect with seed 42 for consistent track

    // Cleanup on unmount
    return () => {
      if (inputIntervalRef.current) {
        clearInterval(inputIntervalRef.current);
      }
      ws.disconnect();
    };
  }, []);

  // Send inputs to server at regular intervals (60 FPS)
  useEffect(() => {
    if (!wsRef.current || !wsRef.current.isConnected()) return;

    // Clear existing interval
    if (inputIntervalRef.current) {
      clearInterval(inputIntervalRef.current);
    }

    // Send inputs at 60 FPS
    inputIntervalRef.current = window.setInterval(() => {
      wsRef.current?.sendInput(inputState);
    }, 1000 / 60);

    return () => {
      if (inputIntervalRef.current) {
        clearInterval(inputIntervalRef.current);
      }
    };
  }, [inputState]);

  const handleStartRace = () => {
    if (wsRef.current && wsRef.current.isConnected()) {
      wsRef.current.startRace();
      setRaceStarted(true);
    }
  };

  if (loading) {
    return (
      <div className="p-8">
        <h2 className="text-3xl font-bold mb-4">Multiplayer Rally Stage</h2>
        <div className="mt-8 bg-gray-800 p-4 rounded-lg text-center py-12">
          <p className="text-xl text-gray-400">Connecting to server...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-8">
        <h2 className="text-3xl font-bold mb-4">Multiplayer Rally Stage</h2>
        <div className="mt-8 bg-red-900/20 border border-red-600 p-4 rounded-lg">
          <p className="text-red-400">Error: {error}</p>
          <button
            onClick={() => window.location.reload()}
            className="mt-4 px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="p-8">
      <h2 className="text-3xl font-bold mb-4">Multiplayer Rally Stage (Server-Authoritative)</h2>
      <div className="mb-4 flex gap-4 items-center">
        <div className="text-gray-300">
          <span className="font-semibold">Session:</span> {sessionId?.substring(0, 8)}...
        </div>
        <div className="text-gray-300">
          <span className="font-semibold">Player ID:</span> {playerId?.substring(0, 8)}...
        </div>
        {!raceStarted && (
          <button
            onClick={handleStartRace}
            className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700"
          >
            Start Race
          </button>
        )}
      </div>

      <p className="text-gray-300 mb-4">
        Physics running on server at 60Hz. Client receives state updates and renders.
      </p>

      <div className="mt-8 bg-gray-800 p-4 rounded-lg relative">
        <GameCanvas gameState={gameState} width={800} height={600} />
        {gameState && <RaceHUD raceInfo={gameState.raceInfo} car={gameState.cars[0]} />}
      </div>

      {/* Keyboard Input Display */}
      <div className="mt-4 bg-gray-800 p-4 rounded-lg">
        <h3 className="text-lg font-semibold mb-3">Keyboard Controls (Sent to Server)</h3>
        <p className="text-sm text-gray-400 mb-3">
          Inputs are sent to server at 60 FPS
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
        <p>Server-Authoritative Features:</p>
        <ul className="list-disc list-inside ml-4 mt-2">
          <li>Server runs physics at fixed 60Hz tick rate</li>
          <li>Client sends inputs at 60 FPS</li>
          <li>Server broadcasts state updates at 60 FPS</li>
          <li>Obstacle collision handled server-side</li>
          <li>Checkpoint progress tracked server-side</li>
          <li>Multi-player support (connect with same session ID)</li>
        </ul>
      </div>
    </div>
  );
}
