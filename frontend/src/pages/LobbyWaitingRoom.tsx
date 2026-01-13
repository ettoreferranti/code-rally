/**
 * Lobby Waiting Room page.
 *
 * Displays lobby members, allows host to configure settings and start race.
 * Uses WebSocket for real-time updates.
 */

import React, { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import type { Lobby, LobbyMember } from '../services';
import { useUsername } from '../hooks/useUsername';
import { getWsBaseUrl } from '../config';

const WS_BASE_URL = getWsBaseUrl();

interface LobbyState extends Lobby {}

const LobbyWaitingRoom: React.FC = () => {
  const { lobbyId } = useParams<{ lobbyId: string }>();
  const navigate = useNavigate();
  const { username, loading: usernameLoading } = useUsername();

  const [lobbyState, setLobbyState] = useState<LobbyState | null>(null);
  const [playerId, setPlayerId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isHost, setIsHost] = useState(false);
  const [isConnected, setIsConnected] = useState(false);

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

        case 'lobby_state':
          // Full lobby state update
          const state: LobbyState = message.data;
          setLobbyState(state);
          // Update isHost if needed
          if (playerId) {
            setIsHost(playerId === state.host_player_id);
          }
          break;

        case 'lobby_member_joined':
          // New member joined - we'll get a lobby_state update
          break;

        case 'lobby_member_left':
          // Member left - we'll get a lobby_state update
          break;

        case 'race_starting':
          // Race is starting - navigate to race page with session and player ID
          const gameSessionId = message.data.game_session_id;
          // Use username directly (it's what we used to join the lobby)
          const playerIdParam = username ? `&player_id=${encodeURIComponent(username)}` : '';
          navigate(`/race?session_id=${gameSessionId}${playerIdParam}`);
          break;

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
  }, [lobbyId, navigate, username, usernameLoading]);

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
            <h1 className="text-4xl font-bold">{lobbyState.name}</h1>
            <button
              onClick={handleLeaveLobby}
              className="px-4 py-2 bg-red-700 hover:bg-red-600 rounded"
            >
              Leave Lobby
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
                  {member.is_bot && (
                    <span className="px-2 py-1 bg-blue-700 text-blue-200 text-xs rounded">
                      BOT
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Host Controls */}
        {isHost ? (
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
