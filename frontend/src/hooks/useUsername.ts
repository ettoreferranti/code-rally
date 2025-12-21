/**
 * Custom hook for managing username in localStorage and backend registration.
 *
 * Handles:
 * - Loading username from localStorage on mount
 * - Prompting user for username if not set
 * - Registering username with backend
 * - Persisting username to localStorage
 */

import { useState, useEffect, useCallback } from 'react';
import { registerUser } from '../services/botApi';

const STORAGE_KEY = 'coderally_username';

export function useUsername() {
  const [username, setUsername] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Load username from localStorage on mount
  useEffect(() => {
    const storedUsername = localStorage.getItem(STORAGE_KEY);
    if (storedUsername) {
      setUsername(storedUsername);
    }
    setLoading(false);
  }, []);

  /**
   * Prompt user for username, validate, and register with backend.
   *
   * @returns Promise that resolves when username is set, or rejects if cancelled/invalid
   */
  const promptAndSetUsername = useCallback(async (): Promise<string> => {
    return new Promise((resolve, reject) => {
      const input = window.prompt(
        'Enter your username (3-50 characters, letters, numbers, dashes, underscores):'
      );

      if (!input) {
        reject(new Error('Username entry cancelled'));
        return;
      }

      const trimmedUsername = input.trim();

      // Basic client-side validation
      if (trimmedUsername.length < 3) {
        setError('Username must be at least 3 characters');
        reject(new Error('Username must be at least 3 characters'));
        return;
      }

      if (trimmedUsername.length > 50) {
        setError('Username must not exceed 50 characters');
        reject(new Error('Username must not exceed 50 characters'));
        return;
      }

      if (!/^[a-zA-Z0-9_-]+$/.test(trimmedUsername)) {
        setError('Username can only contain letters, numbers, dashes, and underscores');
        reject(new Error('Username can only contain letters, numbers, dashes, and underscores'));
        return;
      }

      // Register with backend
      setLoading(true);
      setError(null);

      registerUser(trimmedUsername)
        .then((user) => {
          // Save to localStorage
          localStorage.setItem(STORAGE_KEY, user.username);
          setUsername(user.username);
          setLoading(false);
          resolve(user.username);
        })
        .catch((err) => {
          const errorMessage = err instanceof Error ? err.message : 'Failed to register username';
          setError(errorMessage);
          setLoading(false);
          reject(err);
        });
    });
  }, []);

  /**
   * Clear username from state and localStorage.
   */
  const clearUsername = useCallback(() => {
    localStorage.removeItem(STORAGE_KEY);
    setUsername(null);
    setError(null);
  }, []);

  return {
    username,
    loading,
    error,
    promptAndSetUsername,
    clearUsername,
  };
}
