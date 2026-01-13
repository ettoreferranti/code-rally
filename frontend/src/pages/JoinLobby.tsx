/**
 * Join Lobby page - resolves join code and redirects to lobby.
 *
 * Fetches lobby by join code and redirects to the lobby waiting room.
 */

import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { fetchLobbyByCode } from '../services';

const JoinLobby: React.FC = () => {
  const { code } = useParams<{ code: string }>();
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!code) {
      setError('No join code provided');
      return;
    }

    // Fetch lobby by code and redirect
    fetchLobbyByCode(code)
      .then((lobby) => {
        navigate(`/lobby/${lobby.lobby_id}`);
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : 'Failed to join lobby');
      });
  }, [code, navigate]);

  return (
    <div className="min-h-screen bg-gray-900 text-white flex items-center justify-center">
      <div className="text-center">
        {error ? (
          <div>
            <h1 className="text-3xl font-bold mb-4 text-red-500">Error</h1>
            <p className="text-xl mb-6">{error}</p>
            <button
              onClick={() => navigate('/lobbies')}
              className="px-6 py-3 bg-blue-600 hover:bg-blue-500 rounded-lg"
            >
              Back to Lobby Browser
            </button>
          </div>
        ) : (
          <div>
            <h1 className="text-3xl font-bold mb-4">Joining Lobby...</h1>
            <p className="text-xl text-gray-400">Code: {code?.toUpperCase()}</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default JoinLobby;
