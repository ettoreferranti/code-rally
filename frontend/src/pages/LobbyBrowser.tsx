/**
 * Lobby Browser page.
 *
 * Displays list of available lobbies and allows creating new lobbies.
 */

import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { fetchLobbies, createLobby, disbandLobby, type LobbyListItem } from '../services';
import { useUsername } from '../hooks/useUsername';

const LobbyBrowser: React.FC = () => {
  const navigate = useNavigate();
  const { username } = useUsername();
  const [lobbies, setLobbies] = useState<LobbyListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [newLobbyName, setNewLobbyName] = useState('');
  const [difficulty, setDifficulty] = useState('medium');
  const [maxPlayers, setMaxPlayers] = useState(8);
  const [creating, setCreating] = useState(false);

  // Load lobbies on mount and auto-refresh every 5 seconds
  useEffect(() => {
    loadLobbies();
    const interval = setInterval(loadLobbies, 5000);
    return () => clearInterval(interval);
  }, []);

  const loadLobbies = async () => {
    try {
      // Show waiting (joinable) and racing (spectatable) lobbies
      const [waiting, racing] = await Promise.all([
        fetchLobbies('waiting'),
        fetchLobbies('racing'),
      ]);
      setLobbies([...waiting, ...racing]);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load lobbies');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateLobby = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!newLobbyName.trim()) {
      setError('Lobby name is required');
      return;
    }

    if (!username) {
      setError('You must be logged in to create a lobby');
      return;
    }

    setCreating(true);
    setError(null);

    try {
      // Use username as host player ID (will match WebSocket connection)
      const lobby = await createLobby({
        name: newLobbyName,
        host_player_id: username,
        track_difficulty: difficulty,
        max_players: maxPlayers,
      });

      // Navigate to waiting room
      navigate(`/lobby/${lobby.lobby_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create lobby');
      setCreating(false);
    }
  };

  const handleJoinLobby = (lobbyId: string) => {
    navigate(`/lobby/${lobbyId}`);
  };

  const handleDeleteLobby = async (lobby: LobbyListItem) => {
    if (!username) return;
    const ok = window.confirm(
      `Delete lobby "${lobby.name}"? This cannot be undone.`,
    );
    if (!ok) return;
    setError(null);
    try {
      await disbandLobby(lobby.lobby_id, username);
      await loadLobbies();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete lobby');
    }
  };

  const handleSpectateLobby = (lobby: LobbyListItem) => {
    if (lobby.status === 'racing' && lobby.game_session_id) {
      // Racing lobby - go directly to race as spectator
      navigate(`/race?session_id=${lobby.game_session_id}&spectate=true`);
    } else {
      // Waiting lobby - go to waiting room as spectator
      navigate(`/lobby/${lobby.lobby_id}?spectate=true`);
    }
  };

  if (loading && lobbies.length === 0) {
    return (
      <div className="min-h-screen bg-gray-900 text-white flex items-center justify-center">
        <div className="text-xl">Loading lobbies...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-900 text-white p-8">
      {/* Header */}
      <div className="max-w-6xl mx-auto mb-8">
        <div className="flex justify-between items-center mb-6">
          <h1 className="text-4xl font-bold">Race Lobbies</h1>
          <button
            onClick={() => navigate('/')}
            className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded"
          >
            Back to Home
          </button>
        </div>

        {/* Create Lobby Button */}
        <button
          onClick={() => setCreateDialogOpen(true)}
          className="px-6 py-3 bg-blue-600 hover:bg-blue-500 rounded-lg text-lg font-semibold"
        >
          Create New Lobby
        </button>
      </div>

      {/* Error Message */}
      {error && (
        <div className="max-w-6xl mx-auto mb-6 p-4 bg-red-900 border border-red-700 rounded">
          {error}
        </div>
      )}

      {/* Lobby List */}
      <div className="max-w-6xl mx-auto">
        {lobbies.length === 0 ? (
          <div className="text-center py-12 text-gray-400">
            <p className="text-xl mb-2">No lobbies available</p>
            <p>Create a new lobby to get started!</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {lobbies.map((lobby) => {
              // Use creator (stable) for the "YOUR LOBBY" badge so a host
              // transfer to a bot doesn't make the lobby look like
              // someone else's. Fall back to host_player_id for old
              // payloads that don't have creator_player_id yet.
              const ownerId = lobby.creator_player_id ?? lobby.host_player_id;
              const isOwnLobby = !!username && ownerId === username;
              const isFull = lobby.member_count >= lobby.max_players;
              return (
                <div
                  key={lobby.lobby_id}
                  className={`bg-gray-800 border rounded-lg p-6 transition-colors ${
                    isOwnLobby
                      ? 'border-yellow-600/60 hover:border-yellow-500'
                      : 'border-gray-700 hover:border-blue-500'
                  }`}
                >
                  <div className="flex items-start justify-between mb-2 gap-2">
                    <h3 className="text-xl font-bold flex-1 min-w-0 truncate">{lobby.name}</h3>
                    {isOwnLobby && (
                      <span
                        data-testid="your-lobby-badge"
                        className="px-2 py-0.5 bg-yellow-700 text-yellow-100 text-xs rounded font-semibold"
                      >
                        YOUR LOBBY
                      </span>
                    )}
                  </div>
                  <div className="space-y-1 text-gray-300 mb-4">
                    <p className="text-sm">
                      Created by <span className="font-semibold">{ownerId}</span>
                    </p>
                    <p>
                      Players: {lobby.member_count} / {lobby.max_players}
                    </p>
                    <p className="text-sm">
                      Status:{' '}
                      <span className={lobby.status === 'racing' ? 'text-green-400 font-semibold' : ''}>
                        {lobby.status === 'racing' ? 'In Race' : lobby.status}
                      </span>
                    </p>
                    {lobby.spectator_count > 0 && (
                      <p className="text-sm text-gray-400">
                        Spectators: {lobby.spectator_count}
                      </p>
                    )}
                  </div>
                  <div className="flex gap-2">
                    {lobby.status === 'waiting' && (
                      <button
                        onClick={() => handleJoinLobby(lobby.lobby_id)}
                        disabled={!isOwnLobby && isFull}
                        className={`flex-1 py-2 rounded font-semibold ${
                          isOwnLobby
                            ? 'bg-yellow-700 hover:bg-yellow-600'
                            : isFull
                            ? 'bg-gray-600 cursor-not-allowed'
                            : 'bg-green-600 hover:bg-green-500'
                        }`}
                      >
                        {isOwnLobby ? 'Resume' : isFull ? 'Full' : 'Join'}
                      </button>
                    )}
                    <button
                      onClick={() => handleSpectateLobby(lobby)}
                      className={`${lobby.status === 'racing' ? 'flex-1' : ''} py-2 px-4 rounded font-semibold bg-purple-600 hover:bg-purple-500`}
                    >
                      Spectate
                    </button>
                    {isOwnLobby && (
                      <button
                        data-testid={`delete-lobby-${lobby.lobby_id}`}
                        onClick={() => handleDeleteLobby(lobby)}
                        title="Delete this lobby"
                        className="py-2 px-3 rounded font-semibold bg-red-700 hover:bg-red-600"
                      >
                        🗑️
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Create Lobby Dialog */}
      {createDialogOpen && (
        <div className="fixed inset-0 bg-black bg-opacity-75 flex items-center justify-center p-4">
          <div className="bg-gray-800 rounded-lg p-6 max-w-md w-full">
            <h2 className="text-2xl font-bold mb-4">Create New Lobby</h2>

            <form onSubmit={handleCreateLobby}>
              {/* Lobby Name */}
              <div className="mb-4">
                <label className="block text-sm font-semibold mb-2">Lobby Name</label>
                <input
                  type="text"
                  value={newLobbyName}
                  onChange={(e) => setNewLobbyName(e.target.value)}
                  className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded focus:outline-none focus:border-blue-500"
                  placeholder="Enter lobby name"
                  maxLength={50}
                  required
                />
              </div>

              {/* Difficulty */}
              <div className="mb-4">
                <label className="block text-sm font-semibold mb-2">Track Difficulty</label>
                <select
                  value={difficulty}
                  onChange={(e) => setDifficulty(e.target.value)}
                  className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded focus:outline-none focus:border-blue-500"
                >
                  <option value="easy">Easy</option>
                  <option value="medium">Medium</option>
                  <option value="hard">Hard</option>
                  <option value="extreme">Extreme</option>
                </select>
              </div>

              {/* Max Players */}
              <div className="mb-6">
                <label className="block text-sm font-semibold mb-2">
                  Max Players: {maxPlayers}
                </label>
                <input
                  type="range"
                  min="2"
                  max="8"
                  value={maxPlayers}
                  onChange={(e) => setMaxPlayers(Number(e.target.value))}
                  className="w-full"
                />
              </div>

              {/* Buttons */}
              <div className="flex gap-3">
                <button
                  type="button"
                  onClick={() => {
                    setCreateDialogOpen(false);
                    setNewLobbyName('');
                    setError(null);
                  }}
                  disabled={creating}
                  className="flex-1 px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded disabled:opacity-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={creating}
                  className="flex-1 px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded font-semibold disabled:opacity-50"
                >
                  {creating ? 'Creating...' : 'Create'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default LobbyBrowser;
