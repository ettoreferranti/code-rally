/**
 * Lobby Waiting Room page.
 *
 * Displays lobby members, allows host to configure settings and start race.
 * Uses WebSocket for real-time updates.
 */

import React, { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import type { Lobby, LobbyMember } from '../services';
import { useUsername } from '../hooks/useUsername';
import { getWsBaseUrl } from '../config';

const WS_BASE_URL = getWsBaseUrl();

interface LobbyState extends Lobby {}

const LobbyWaitingRoom: React.FC = () => {
  const { lobbyId } = useParams<{ lobbyId: string }>();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const isSpectator = searchParams.get('spectate') === 'true';
  const { username, loading: usernameLoading } = useUsername();

  const [lobbyState, setLobbyState] = useState<LobbyState | null>(null);
  const [playerId, setPlayerId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isHost, setIsHost] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const [llmModelPath, setLlmModelPath] = useState<string>('');

  const wsRef = useRef<WebSocket | null>(null);

  // Connect to WebSocket on mount
  useEffect(() => {
    if (!lobbyId) return;

    // Wait for username to load before connecting
    if (usernameLoading) return;

    // Build WebSocket URL with lobby_id and optional player_id (username)
    let wsUrl = `${WS_BASE_URL}/game/ws?lobby_id=${lobbyId}`;
    if (username) {
      wsUrl += `&player_id=${encodeURIComponent(username)}`;
    }
    if (isSpectator) {
      wsUrl += '&spectate=true';
    }

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      console.log('Connected to lobby WebSocket');
      setIsConnected(true);
      setError(null); // Clear any previous errors
    };

    ws.onmessage = (event) => {
      const message = JSON.parse(event.data);
      console.log('WebSocket message:', message);

      // Clear error on successful message (connection is working)
      if (error) {
        setError(null);
      }

      switch (message.type) {
        case 'lobby_joined':
          // Successfully joined lobby - we get our player_id and initial lobby state
          setPlayerId(message.data.player_id);
          setLobbyState(message.data.lobby);
          setIsHost(message.data.player_id === message.data.lobby.host_player_id);
          break;

        case 'spectator_joined':
          // Successfully joined as spectator
          setPlayerId(message.data.player_id);
          setLobbyState(message.data.lobby);
          setIsHost(false);
          break;

        case 'lobby_state':
          // Full lobby state update
          const state: LobbyState = message.data;
          setLobbyState(state);
          // Update isHost if needed (spectators are never host)
          if (playerId && !isSpectator) {
            setIsHost(playerId === state.host_player_id);
          }
          break;

        case 'lobby_member_joined':
          // New member joined - we'll get a lobby_state update
          break;

        case 'lobby_member_left':
          // Member left - we'll get a lobby_state update
          break;

        case 'race_starting': {
          // Race is starting - navigate to race page with session and player ID
          const gameSessionId = message.data.game_session_id;
          const playerIdParam = username ? `&player_id=${encodeURIComponent(username)}` : '';
          const spectateParam = isSpectator ? '&spectate=true' : '';
          navigate(`/race?session_id=${gameSessionId}${playerIdParam}${spectateParam}`);
          break;
        }

        case 'error':
          setError(message.data.message);
          break;
      }
    };

    ws.onerror = (err) => {
      console.error('WebSocket error:', err);
      setError('Connection error');
    };

    ws.onclose = () => {
      console.log('WebSocket closed');
      setIsConnected(false);
    };

    return () => {
      // Only send leave message if connection is fully open
      if (ws.readyState === WebSocket.OPEN) {
        try {
          ws.send(JSON.stringify({ type: 'leave_lobby' }));
        } catch (err) {
          console.error('Failed to send leave message:', err);
        }
      }
      // Close connection if not already closed
      if (ws.readyState !== WebSocket.CLOSED && ws.readyState !== WebSocket.CLOSING) {
        ws.close();
      }
    };
  }, [lobbyId, navigate, username, usernameLoading, isSpectator]);

  const handleStartRace = () => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      setError('Not connected to server');
      return;
    }

    wsRef.current.send(
      JSON.stringify({
        type: 'start_race',
      })
    );
  };

  const handleAddLlmBot = () => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      setError('Not connected to server');
      return;
    }

    const trimmed = llmModelPath.trim();
    wsRef.current.send(
      JSON.stringify({
        type: 'add_llm_bot_to_lobby',
        data: trimmed ? { model_path: trimmed } : {},
      })
    );
  };

  const handleLeaveLobby = () => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'leave_lobby' }));
    }
    navigate('/lobbies');
  };

  if (!lobbyState) {
    return (
      <div className="min-h-screen bg-gray-900 text-white flex items-center justify-center">
        <div className="text-xl">
          {usernameLoading
            ? 'Loading user...'
            : isConnected
              ? 'Loading lobby...'
              : 'Connecting...'}
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-900 text-white p-8">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <div className="flex justify-between items-center mb-4">
            <div className="flex items-center gap-3">
              <h1 className="text-4xl font-bold">{lobbyState.name}</h1>
              {isSpectator && (
                <span className="px-3 py-1 bg-purple-700 text-purple-200 text-sm rounded font-semibold">
                  SPECTATING
                </span>
              )}
            </div>
            <button
              onClick={handleLeaveLobby}
              className="px-4 py-2 bg-red-700 hover:bg-red-600 rounded"
            >
              {isSpectator ? 'Stop Spectating' : 'Leave Lobby'}
            </button>
          </div>

          {/* Join Code */}
          <div className="mb-4 flex items-center gap-3">
            <span className="text-sm text-gray-400">Join Code:</span>
            <code className="text-2xl font-mono font-bold text-green-400 px-3 py-1 bg-gray-800 rounded">
              {lobbyState.join_code}
            </code>
            <button
              onClick={() => {
                navigator.clipboard.writeText(lobbyState.join_code);
              }}
              className="px-3 py-1 bg-blue-600 hover:bg-blue-500 rounded text-sm"
              title="Copy join code"
            >
              Copy
            </button>
          </div>

          <div className="flex items-center gap-4 text-gray-300">
            <span>
              Players: {lobbyState.members.length} / {lobbyState.settings.max_players}
            </span>
            {(lobbyState.spectator_count > 0) && (
              <>
                <span>•</span>
                <span className="text-purple-400">
                  Spectators: {lobbyState.spectator_count}
                </span>
              </>
            )}
            <span>•</span>
            <span>Difficulty: {lobbyState.settings.track_difficulty}</span>
            {isHost && (
              <>
                <span>•</span>
                <span className="text-yellow-400">You are the host</span>
              </>
            )}
          </div>
        </div>

        {/* Error Message */}
        {error && (
          <div className="mb-6 p-4 bg-red-900 border border-red-700 rounded">
            {error}
          </div>
        )}

        {/* Members List */}
        <div className="mb-8">
          <h2 className="text-2xl font-bold mb-4">Players</h2>
          <div className="bg-gray-800 border border-gray-700 rounded-lg divide-y divide-gray-700">
            {lobbyState.members.map((member) => (
              <div
                key={member.player_id}
                className="p-4 flex items-center justify-between"
              >
                <div className="flex items-center gap-3">
                  {/* Ready Indicator */}
                  <div
                    className={`w-3 h-3 rounded-full ${
                      member.ready ? 'bg-green-500' : 'bg-gray-500'
                    }`}
                  />

                  {/* Player Name */}
                  <span className="font-semibold">
                    {member.username || member.player_id.substring(0, 8)}
                  </span>

                  {/* Badges */}
                  {member.player_id === lobbyState.host_player_id && (
                    <span className="px-2 py-1 bg-yellow-700 text-yellow-200 text-xs rounded">
                      HOST
                    </span>
                  )}
                  {member.driver_kind === 'llm_bot' ? (
                    <span
                      data-testid="llm-bot-badge"
                      className="px-2 py-1 bg-purple-700 text-purple-200 text-xs rounded"
                      title={member.llm_model_path || 'default model'}
                    >
                      LLM
                    </span>
                  ) : member.is_bot ? (
                    <span className="px-2 py-1 bg-blue-700 text-blue-200 text-xs rounded">
                      BOT
                    </span>
                  ) : null}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Host Controls / Waiting Messages */}
        {isSpectator ? (
          <div className="text-center py-12">
            <p className="text-xl text-purple-400">
              Spectating - waiting for race to start...
            </p>
          </div>
        ) : isHost ? (
          <div className="mb-8">
            <h2 className="text-2xl font-bold mb-4">Host Controls</h2>
            <div className="bg-gray-800 border border-gray-700 rounded-lg p-6">
              {/* Settings Display */}
              <div className="mb-6 space-y-2 text-gray-300">
                <p>
                  <span className="font-semibold">Track Difficulty:</span>{' '}
                  {lobbyState.settings.track_difficulty}
                </p>
                <p>
                  <span className="font-semibold">Track Seed:</span>{' '}
                  {lobbyState.settings.track_seed || 'Random'}
                </p>
                <p>
                  <span className="font-semibold">Max Players:</span>{' '}
                  {lobbyState.settings.max_players}
                </p>
              </div>

              {/* Add LLM Bot — research playground (#157) */}
              <div className="mb-4 p-3 bg-gray-900 rounded border border-purple-700/40">
                <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
                  <input
                    data-testid="llm-model-input"
                    type="text"
                    value={llmModelPath}
                    onChange={(e) => setLlmModelPath(e.target.value)}
                    placeholder="model path (default: Qwen2.5-1.5B-Instruct-4bit)"
                    className="flex-1 px-3 py-2 bg-gray-800 border border-gray-700 rounded text-sm"
                  />
                  <button
                    data-testid="add-llm-bot-button"
                    onClick={handleAddLlmBot}
                    disabled={lobbyState.members.length >= lobbyState.settings.max_players}
                    className="px-4 py-2 bg-purple-700 hover:bg-purple-600 rounded text-sm font-semibold disabled:bg-gray-600 disabled:cursor-not-allowed whitespace-nowrap"
                  >
                    Add LLM Bot
                  </button>
                </div>
              </div>

              {/* Start Race Button */}
              <button
                onClick={handleStartRace}
                disabled={lobbyState.members.length < 1}
                className="w-full py-3 bg-green-600 hover:bg-green-500 rounded-lg text-lg font-bold disabled:bg-gray-600 disabled:cursor-not-allowed"
              >
                {lobbyState.members.length < 1
                  ? 'Need at least 1 player'
                  : 'Start Race'}
              </button>
            </div>
          </div>
        ) : (
          /* Non-Host Waiting Message */
          <div className="text-center py-12">
            <p className="text-xl text-gray-400">
              Waiting for host to start race...
            </p>
          </div>
        )}

        {/* Connection Status */}
        <div className="text-center text-sm text-gray-500">
          {isConnected ? (
            <span className="text-green-500">● Connected</span>
          ) : (
            <span className="text-red-500">● Disconnected</span>
          )}
        </div>
      </div>
    </div>
  );
};

export default LobbyWaitingRoom;
