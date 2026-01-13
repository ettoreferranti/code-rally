/**
 * Lobby Browser page.
 *
 * Displays list of available lobbies and allows creating new lobbies.
 */

import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { fetchLobbies, createLobby, type LobbyListItem } from '../services';

const LobbyBrowser: React.FC = () => {
  const navigate = useNavigate();
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
      // Only show waiting lobbies (joinable)
      const data = await fetchLobbies('waiting');
      setLobbies(data);
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

    setCreating(true);
    setError(null);

    try {
      // Generate a temporary player ID (will be replaced by WebSocket)
      const tempPlayerId = `player-${Date.now()}`;

      const lobby = await createLobby({
        name: newLobbyName,
        host_player_id: tempPlayerId,
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
            {lobbies.map((lobby) => (
              <div
                key={lobby.lobby_id}
                className="bg-gray-800 border border-gray-700 rounded-lg p-6 hover:border-blue-500 transition-colors"
              >
                <h3 className="text-xl font-bold mb-2">{lobby.name}</h3>
                <div className="space-y-1 text-gray-300 mb-4">
                  <p>
                    Players: {lobby.member_count} / {lobby.max_players}
                  </p>
                  <p className="text-sm">Status: {lobby.status}</p>
                </div>
                <button
                  onClick={() => handleJoinLobby(lobby.lobby_id)}
                  disabled={lobby.member_count >= lobby.max_players}
                  className={`w-full py-2 rounded font-semibold ${
                    lobby.member_count >= lobby.max_players
                      ? 'bg-gray-600 cursor-not-allowed'
                      : 'bg-green-600 hover:bg-green-500'
                  }`}
                >
                  {lobby.member_count >= lobby.max_players ? 'Full' : 'Join Lobby'}
                </button>
              </div>
            ))}
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
