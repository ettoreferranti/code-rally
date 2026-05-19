import { useState, useEffect, useRef, useMemo } from 'react';
import { GameCanvas, useKeyboardInput } from '../game';
import type { GameState, Track, PlayerResult, InputState } from '../game/types';
import { RaceHUD } from '../components/RaceHUD';
import { CountdownOverlay } from '../components/CountdownOverlay';
import { RaceResultsScreen } from '../components/RaceResultsScreen';
import { GameWebSocketClient, type GameStateMessage } from '../services';

export default function MultiplayerRace() {
  const [track, setTrack] = useState<Track | null>(null);
  const [gameState, setGameState] = useState<GameState | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [playerId, setPlayerId] = useState<string | null>(null);
  const [raceStarted, setRaceStarted] = useState(false);
  const [raceResults, setRaceResults] = useState<PlayerResult[] | null>(null);
  const [showResults, setShowResults] = useState(false);

  // Parse seed and session_id from URL (memoized to only calculate once)
  const seed = useMemo(() => {
    const urlParams = new URLSearchParams(window.location.search);
    const seedParam = urlParams.get('seed');
    return seedParam ? parseInt(seedParam, 10) : Math.floor(Math.random() * 1000000);
  }, []);

  const sessionIdFromUrl = useMemo(() => {
    const urlParams = new URLSearchParams(window.location.search);
    return urlParams.get('session_id') || undefined;
  }, []);

  const playerIdFromUrl = useMemo(() => {
    const urlParams = new URLSearchParams(window.location.search);
    return urlParams.get('player_id') || undefined;
  }, []);

  const isSpectator = useMemo(() => {
    const urlParams = new URLSearchParams(window.location.search);
    return urlParams.get('spectate') === 'true';
  }, []);

  // Spectator camera state
  const [cameraMode, setCameraMode] = useState<'follow' | 'free'>('follow');
  const [followTarget, setFollowTarget] = useState<string | null>(null);

  const inputState = useKeyboardInput();
  const wsRef = useRef<GameWebSocketClient | null>(null);
  const inputIntervalRef = useRef<number | null>(null);
  const trackRef = useRef<Track | null>(null);
  const playerIdRef = useRef<string | null>(null);
  const hasShownResultsRef = useRef<boolean>(false);
  const hasClosedResultsRef = useRef<boolean>(false);
  const lastInputRef = useRef<InputState>({
    accelerate: false,
    brake: false,
    turnLeft: false,
    turnRight: false,
    nitro: false,
  });

  // Game state updates every tick (60 FPS) - no need to log this

  // (Bot-library fetch removed — bots are added pre-race in the lobby.)

  // Initialize WebSocket connection
  useEffect(() => {
    const ws = new GameWebSocketClient({
      onConnected: (sid, pid, receivedTrack) => {
        console.log('Connected to game session:', sid);
        setSessionId(sid);
        setPlayerId(pid);
        setTrack(receivedTrack);

        // Update refs for use in callbacks
        trackRef.current = receivedTrack;
        playerIdRef.current = pid;

        setLoading(false);
        setError(null);  // Clear any previous errors
      },

      onGameState: (state: GameStateMessage['data']) => {
        // Use refs to get current values (avoids closure issue)
        const currentTrack = trackRef.current;
        const currentPlayerId = playerIdRef.current;

        // Convert server state to frontend GameState format
        if (!currentTrack) {
          console.warn('Missing track, skipping game state update');
          return;
        }

        // For spectators, use the first player's data as reference for race info
        const playerIds = Object.keys(state.players);
        const playerData = currentPlayerId ? state.players[currentPlayerId] : null;
        const referencePlayer = playerData || (playerIds.length > 0 ? state.players[playerIds[0]] : null);

        if (!referencePlayer) {
          return;
        }

        const newGameState: GameState = {
          track: currentTrack,
          cars: Object.entries(state.players).map(([pid, pData]) => ({
            position: pData.car.position,
            velocity: pData.car.velocity,
            heading: pData.car.heading,
            angular_velocity: pData.car.angular_velocity,
            is_drifting: pData.car.is_drifting,
            drift_angle: pData.car.drift_angle,
            throttle: 0,  // Not tracked server-side yet
            is_off_track: pData.is_off_track,
            nitro_charges: pData.car.nitro_charges,
            nitro_active: pData.car.nitro_active,
            nitro_remaining_ticks: pData.car.nitro_remaining_ticks,
            isCurrentPlayer: pid === currentPlayerId,
            playerId: pid,
            isBot: pData.is_bot,
            botName: pData.bot_name,
            agentIntent: pData.agent_intent,
          })),
          tick: state.tick,
          spectatorCount: (state as any).spectator_count || 0,
          raceInfo: {
            currentCheckpoint: referencePlayer.current_checkpoint,
            totalCheckpoints: currentTrack.checkpoints.length,
            isFinished: referencePlayer.is_finished,
            finishTime: referencePlayer.finish_time,
            startTime: state.race_info.start_time,
            countdownRemaining: state.race_info.countdown_remaining,
            raceStatus: state.race_info.status,
            firstFinisherTime: state.race_info.first_finisher_time,
            gracePeriodRemaining: state.race_info.grace_period_remaining,
            currentPosition: referencePlayer.position,
            totalPlayers: Object.keys(state.players).length,
          }
        };

        setGameState(newGameState);

        // Check if race has finished and collect results
        if (state.race_info.status === 'finished' && !hasShownResultsRef.current && !hasClosedResultsRef.current) {
          const startTime = state.race_info.start_time;
          const results: PlayerResult[] = Object.entries(state.players).map(([pid, player]) => ({
            playerId: pid,
            position: player.position,
            // Calculate race duration: finish_time - start_time (both are absolute timestamps)
            finishTime: player.finish_time && startTime ? player.finish_time - startTime : null,
            points: player.points,
            dnf: player.dnf,
          }));
          setRaceResults(results);
          setShowResults(true);
          hasShownResultsRef.current = true;
        }

        // Reset flags when race restarts
        if (state.race_info.status === 'waiting' && (hasShownResultsRef.current || hasClosedResultsRef.current)) {
          hasShownResultsRef.current = false;
          hasClosedResultsRef.current = false;
        }
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
    ws.connect(sessionIdFromUrl, 'medium', seed, playerIdFromUrl, isSpectator);  // Connect with session and player ID from URL

    // Cleanup on unmount
    return () => {
      if (inputIntervalRef.current) {
        clearInterval(inputIntervalRef.current);
      }
      ws.disconnect();
    };
  }, []);

  // Send inputs to server only when they change
  useEffect(() => {
    if (!wsRef.current || !wsRef.current.isConnected()) {
      return;
    }

    // Don't send inputs during countdown or waiting
    if (gameState?.raceInfo.raceStatus === 'countdown' || gameState?.raceInfo.raceStatus === 'waiting') {
      return;
    }

    // Check if input state has changed
    const lastInput = lastInputRef.current;
    const hasChanged =
      inputState.accelerate !== lastInput.accelerate ||
      inputState.brake !== lastInput.brake ||
      inputState.turnLeft !== lastInput.turnLeft ||
      inputState.turnRight !== lastInput.turnRight ||
      inputState.nitro !== lastInput.nitro;

    if (hasChanged) {
      wsRef.current.sendInput(inputState);
      lastInputRef.current = { ...inputState };
    }
  }, [inputState, gameState?.raceInfo.raceStatus]);

  const handleStartRace = () => {
    console.log('Start Race clicked');
    if (wsRef.current && wsRef.current.isConnected()) {
      console.log('Sending start race command...');
      hasShownResultsRef.current = false;
      hasClosedResultsRef.current = false;
      wsRef.current.startRace();
      setRaceStarted(true);
    } else {
      console.log('WebSocket not connected!');
    }
  };

  const handleCloseResults = () => {
    console.log('Closing results screen');
    setShowResults(false);
    setRaceResults(null);
    setRaceStarted(false);
    hasClosedResultsRef.current = true;  // Prevent results from reopening until race restarts
  };

  const handleShareSession = () => {
    if (!sessionId) return;

    const url = new URL(window.location.href);
    url.searchParams.set('session_id', sessionId);
    url.searchParams.set('seed', seed.toString());

    const isLocalhost = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';

    navigator.clipboard.writeText(url.toString()).then(() => {
      if (isLocalhost) {
        alert(`⚠️ Link copied! Note: You're using localhost.\n\nFor network access, replace 'localhost' with your IP address (e.g., 172.16.1.133) in the link:\n\n${url.toString()}`);
      } else {
        alert('✅ Session link copied to clipboard! Share it with others to race together.');
      }
    }).catch(() => {
      alert(`Share this link: ${url.toString()}`);
    });
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

  // Get list of player IDs for spectator follow target selection
  const playerList = gameState ? gameState.cars
    .filter(car => car.playerId)
    .map(car => ({
      id: car.playerId!,
      name: car.botName || car.playerId!.substring(0, 12),
      isBot: car.isBot,
    })) : [];

  return (
    <div className="p-8">
      <div className="flex items-center gap-3 mb-4">
        <h2 className="text-3xl font-bold">Multiplayer Rally Stage</h2>
        {isSpectator && (
          <span className="px-3 py-1 bg-purple-700 text-purple-200 text-sm rounded font-semibold">
            SPECTATING
          </span>
        )}
      </div>
      <div className="mb-4 flex gap-4 items-center flex-wrap">
        <div className="text-gray-300">
          <span className="font-semibold">Session:</span> {sessionId?.substring(0, 8)}...
        </div>
        {!isSpectator && (
          <div className="text-gray-300">
            <span className="font-semibold">Player ID:</span> {playerId?.substring(0, 8)}...
          </div>
        )}
        <div className="text-gray-300">
          <span className="font-semibold">Players:</span> {gameState?.raceInfo.totalPlayers || 0}
        </div>
        {(gameState?.spectatorCount ?? 0) > 0 && (
          <div className="text-purple-400">
            <span className="font-semibold">Spectators:</span> {gameState?.spectatorCount}
          </div>
        )}
        {!isSpectator && (
          <>
            <div className="text-gray-300">
              <span className="font-semibold">Track Seed:</span> {seed}
              <button
                onClick={() => navigator.clipboard.writeText(seed.toString())}
                className="ml-2 px-2 py-1 text-xs bg-gray-700 rounded hover:bg-gray-600"
                title="Copy seed to clipboard"
              >
                Copy
              </button>
            </div>
            <button
              onClick={handleShareSession}
              className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
              title="Copy shareable session link to clipboard"
            >
              Share Session
            </button>
            {!raceStarted && (
              <button
                onClick={handleStartRace}
                className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700"
              >
                Start Race
              </button>
            )}
            {/* Mid-race bot submission was removed in the Tinker / lobby
                cleanup — all bots are added pre-race in the lobby. */}
            <button
              onClick={() => window.location.reload()}
              className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
              title="Generate new random track"
            >
              New Track
            </button>
          </>
        )}
      </div>

      {/* Spectator Camera Controls */}
      {isSpectator && gameState && playerList.length > 0 && (
        <div className="mb-4 flex gap-4 items-center flex-wrap bg-gray-800 p-3 rounded-lg">
          <span className="font-semibold text-gray-300">Camera:</span>
          <button
            onClick={() => setCameraMode('follow')}
            className={`px-3 py-1 rounded ${cameraMode === 'follow' ? 'bg-purple-600' : 'bg-gray-700 hover:bg-gray-600'}`}
          >
            Follow Car
          </button>
          <button
            onClick={() => setCameraMode('free')}
            className={`px-3 py-1 rounded ${cameraMode === 'free' ? 'bg-purple-600' : 'bg-gray-700 hover:bg-gray-600'}`}
          >
            Free Camera
          </button>
          {cameraMode === 'follow' && (
            <>
              <span className="text-gray-400">|</span>
              <span className="text-gray-300 text-sm">Following:</span>
              <select
                value={followTarget || ''}
                onChange={(e) => setFollowTarget(e.target.value || null)}
                className="px-3 py-1 bg-gray-700 text-white rounded border border-gray-600 text-sm"
              >
                <option value="">Race Leader</option>
                {playerList.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}{p.isBot ? ' (Bot)' : ''}
                  </option>
                ))}
              </select>
              <button
                onClick={() => {
                  const idx = playerList.findIndex(p => p.id === followTarget);
                  const prevIdx = idx <= 0 ? playerList.length - 1 : idx - 1;
                  setFollowTarget(playerList[prevIdx].id);
                }}
                className="px-2 py-1 bg-gray-700 hover:bg-gray-600 rounded text-sm"
                title="Previous car"
              >
                Prev
              </button>
              <button
                onClick={() => {
                  const idx = playerList.findIndex(p => p.id === followTarget);
                  const nextIdx = idx >= playerList.length - 1 ? 0 : idx + 1;
                  setFollowTarget(playerList[nextIdx].id);
                }}
                className="px-2 py-1 bg-gray-700 hover:bg-gray-600 rounded text-sm"
                title="Next car"
              >
                Next
              </button>
            </>
          )}
          {cameraMode === 'free' && (
            <span className="text-gray-400 text-sm">Use WASD to pan camera</span>
          )}
        </div>
      )}

      {!isSpectator && (
        <p className="text-gray-300 mb-4">
          Physics running on server at 60Hz. Click "Share Session" to race with friends in real-time!
        </p>
      )}

      <div className="mt-8 bg-gray-800 p-4 rounded-lg relative">
        <GameCanvas
          gameState={gameState}
          width={800}
          height={600}
          isSpectator={isSpectator}
          spectatorTarget={followTarget}
          cameraMode={cameraMode}
        />
        {gameState && <RaceHUD raceInfo={gameState.raceInfo} car={gameState.cars[0]} />}
        {gameState && (
          <CountdownOverlay
            countdown={gameState.raceInfo.countdownRemaining}
            isVisible={gameState.raceInfo.raceStatus === 'countdown'}
            raceStatus={gameState.raceInfo.raceStatus}
            isFinished={gameState.raceInfo.isFinished}
          />
        )}
        {showResults && raceResults && playerId && (
          <RaceResultsScreen
            results={raceResults}
            currentPlayerId={playerId}
            onClose={handleCloseResults}
          />
        )}
      </div>

      {/* Keyboard Input Display (hidden for spectators) */}
      {!isSpectator && (
        <div className="mt-4 bg-gray-800 p-4 rounded-lg">
          <h3 className="text-lg font-semibold mb-3">Keyboard Controls (Sent to Server)</h3>
          <p className="text-sm text-gray-400 mb-3">
            {gameState?.raceInfo.raceStatus === 'countdown' || gameState?.raceInfo.raceStatus === 'waiting' ? (
              <span className="text-yellow-400 font-semibold">Controls locked during countdown</span>
            ) : (
              <span>Inputs sent only when changed (optimized network traffic)</span>
            )}
          </p>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            <div className={`p-3 rounded text-center transition-colors ${
              inputState.accelerate ? 'bg-green-600' : 'bg-gray-700'
            }`}>
              <div className="font-semibold">Accelerate</div>
              <div className="text-sm text-gray-300">W / Up</div>
            </div>
            <div className={`p-3 rounded text-center transition-colors ${
              inputState.brake ? 'bg-red-600' : 'bg-gray-700'
            }`}>
              <div className="font-semibold">Brake</div>
              <div className="text-sm text-gray-300">S / Down</div>
            </div>
            <div className={`p-3 rounded text-center transition-colors ${
              inputState.turnLeft ? 'bg-blue-600' : 'bg-gray-700'
            }`}>
              <div className="font-semibold">Turn Left</div>
              <div className="text-sm text-gray-300">A / Left</div>
            </div>
            <div className={`p-3 rounded text-center transition-colors ${
              inputState.turnRight ? 'bg-blue-600' : 'bg-gray-700'
            }`}>
              <div className="font-semibold">Turn Right</div>
              <div className="text-sm text-gray-300">D / Right</div>
            </div>
            <div className={`p-3 rounded text-center transition-colors ${
              inputState.nitro ? 'bg-purple-600' : 'bg-gray-700'
            }`}>
              <div className="font-semibold">Nitro</div>
              <div className="text-sm text-gray-300">Space</div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
