/**
 * Reusable user-selection modal: list existing users, create new, delete.
 *
 * Extracted from Editor.tsx so the same UX can be triggered from anywhere
 * in the app (currently: the header UserMenu, plus the Editor's auto-prompt
 * when no username is set).
 *
 * The full-page reload on successful selection/create is intentional —
 * pages that depend on the username (Lobby/Multiplayer/Editor) all rebuild
 * their state from the persisted username on mount, and a reload is the
 * simplest way to ensure no stale connection or bot state carries over.
 */

import { useEffect, useState } from 'react';
import { getAllUsers, registerUser, deleteUser, type User } from '../services/botApi';

interface UserSwitcherModalProps {
  isOpen: boolean;
  onClose: () => void;
  currentUsername: string | null;
  onClearUsername: () => void;
}

export const UserSwitcherModal: React.FC<UserSwitcherModalProps> = ({
  isOpen,
  onClose,
  currentUsername,
  onClearUsername,
}) => {
  const [availableUsers, setAvailableUsers] = useState<User[]>([]);
  const [newUsername, setNewUsername] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Refresh the user list whenever the modal opens.
  useEffect(() => {
    if (!isOpen) return;
    let cancelled = false;
    (async () => {
      try {
        const users = await getAllUsers();
        if (!cancelled) setAvailableUsers(users);
      } catch (err) {
        if (!cancelled) {
          console.error('Failed to load users:', err);
          setAvailableUsers([]);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [isOpen]);

  const handleSelectExistingUser = async (selectedUsername: string) => {
    try {
      setLoading(true);
      const user = await registerUser(selectedUsername);
      localStorage.setItem('coderally_username', user.username);
      onClose();
      window.location.reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to select user');
      setLoading(false);
    }
  };

  const handleCreateNewUser = async () => {
    if (!newUsername.trim()) {
      setError('Please enter a username');
      return;
    }

    try {
      setLoading(true);
      const user = await registerUser(newUsername.trim());
      localStorage.setItem('coderally_username', user.username);
      onClose();
      setNewUsername('');
      window.location.reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create user');
      setLoading(false);
    }
  };

  const handleDeleteUser = async (userToDelete: string, event: React.MouseEvent) => {
    event.stopPropagation();
    if (!confirm(`Delete user "${userToDelete}" and all their bots? This cannot be undone.`)) {
      return;
    }
    try {
      setLoading(true);
      await deleteUser(userToDelete);
      if (userToDelete === currentUsername) {
        onClearUsername();
      }
      // Reload the user list in-place.
      const users = await getAllUsers();
      setAvailableUsers(users);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete user');
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) {
    return null;
  }

  return (
    <div
      data-testid="user-switcher-modal"
      className="fixed inset-0 bg-black bg-opacity-75 flex items-center justify-center z-50"
      onClick={(e) => {
        if (e.target === e.currentTarget && !loading) onClose();
      }}
    >
      <div className="bg-gray-800 rounded-lg p-6 max-w-md w-full mx-4 border border-gray-600">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-2xl font-bold">Select or Create User</h3>
          <button
            onClick={onClose}
            disabled={loading}
            className="text-gray-400 hover:text-white disabled:opacity-50"
            aria-label="Close"
          >
            ✕
          </button>
        </div>

        {availableUsers.length > 0 && (
          <div className="mb-6">
            <h4 className="text-sm font-semibold mb-2 text-gray-300">Existing Users</h4>
            <div className="max-h-48 overflow-y-auto bg-gray-900 rounded border border-gray-700">
              {availableUsers.map((user) => (
                <div
                  key={user.id}
                  className="flex items-center justify-between px-4 py-3 hover:bg-gray-700 transition border-b border-gray-700 last:border-b-0"
                >
                  <button
                    onClick={() => handleSelectExistingUser(user.username)}
                    className="flex-1 text-left"
                    disabled={loading}
                  >
                    <div className="font-semibold text-white">{user.username}</div>
                    <div className="text-xs text-gray-400">
                      Created {new Date(user.created_at).toLocaleDateString()}
                    </div>
                  </button>
                  <button
                    onClick={(e) => handleDeleteUser(user.username, e)}
                    className="ml-3 px-2 py-1 bg-red-600 text-white text-xs rounded hover:bg-red-700 transition disabled:opacity-50"
                    disabled={loading}
                    title="Delete this user and all their bots"
                  >
                    🗑️ Delete
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="mb-4">
          <h4 className="text-sm font-semibold mb-2 text-gray-300">Create New User</h4>
          <input
            type="text"
            value={newUsername}
            onChange={(e) => setNewUsername(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleCreateNewUser()}
            placeholder="Enter new username (3-50 chars)"
            className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded text-white disabled:opacity-50"
            disabled={loading}
          />
          <p className="text-xs text-gray-400 mt-1">
            Letters, numbers, dashes, and underscores only
          </p>
        </div>

        <div className="flex gap-3">
          <button
            onClick={handleCreateNewUser}
            className="flex-1 px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700 transition disabled:opacity-50 disabled:cursor-not-allowed"
            disabled={loading || !newUsername.trim()}
          >
            ➕ Create User
          </button>
        </div>

        {error && (
          <div className="mt-4 px-3 py-2 bg-red-900/50 text-red-400 rounded border border-red-600 text-sm">
            {error}
          </div>
        )}

        {loading && (
          <div className="mt-4 text-center text-gray-400 text-sm">⏳ Loading...</div>
        )}
      </div>
    </div>
  );
};

export default UserSwitcherModal;
