/**
 * Tests for bot submission functionality in MultiplayerRace component.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import MultiplayerRace from './MultiplayerRace';
import { GameWebSocketClient } from '../services/gameWebSocket';

// Mock the bot API

// Mock the WebSocket client
vi.mock('../services/gameWebSocket', () => {
  return {
    GameWebSocketClient: vi.fn(function(this: any, callbacks: any) {
      this.callbacks = callbacks;
      this.connect = vi.fn();
      this.disconnect = vi.fn();
      this.sendInput = vi.fn();
      this.startRace = vi.fn();
      this.sendBot = vi.fn();
      this.isConnected = vi.fn(() => true);
      return this;
    }),
  };
});

// Mock the game components
vi.mock('../game', () => ({
  GameCanvas: () => <div data-testid="game-canvas">Game Canvas</div>,
  useKeyboardInput: () => ({
    accelerate: false,
    brake: false,
    turnLeft: false,
    turnRight: false,
    nitro: false,
  }),
}));

// Mock other components
vi.mock('../components/RaceHUD', () => ({
  RaceHUD: () => <div data-testid="race-hud">HUD</div>,
}));

vi.mock('../components/CountdownOverlay', () => ({
  CountdownOverlay: () => <div data-testid="countdown-overlay">Countdown</div>,
}));

vi.mock('../components/RaceResultsScreen', () => ({
  RaceResultsScreen: () => <div data-testid="race-results">Results</div>,
}));

// Mock useUsername hook
vi.mock('../hooks/useUsername', () => ({
  useUsername: () => ({ username: 'testuser' }),
}));

// The MultiplayerRace - Bot Submission describe block was deleted in
// the Tinker / lobby cleanup (phase 7). Bots are added pre-race via the
// lobby's unified Add bot dropdown; the in-race Submit Bot UI is gone.

describe('MultiplayerRace - Spectator Mode', () => {
  let mockWsInstance: any;
  let mockCallbacks: any;
  let originalSearch: string;

  const setUrlSpectate = (value: boolean) => {
    const search = value ? '?spectate=true' : '';
    window.history.replaceState({}, '', `${window.location.pathname}${search}`);
  };

  const simulateConnect = () => {
    vi.mocked(GameWebSocketClient).mockImplementation(function(this: any, callbacks: any) {
      mockCallbacks = callbacks;
      mockWsInstance = this;
      this.callbacks = callbacks;
      this.connect = vi.fn((sessionId, _difficulty, _seed, _playerId, _spectate) => {
        setTimeout(() => {
          callbacks.onConnected?.(sessionId || 'test-session-id', 'test-player-id', {
            segments: [],
            checkpoints: [],
            start_position: [0, 0],
            start_heading: 0,
            obstacles: [],
            containment: null,
          } as any);
        }, 0);
      });
      this.disconnect = vi.fn();
      this.sendInput = vi.fn();
      this.startRace = vi.fn();
      this.sendBot = vi.fn();
      this.isConnected = vi.fn(() => true);
      return this;
    } as any);
  };

  beforeEach(() => {
    vi.clearAllMocks();
    originalSearch = window.location.search;
    simulateConnect();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    window.history.replaceState({}, '', `${window.location.pathname}${originalSearch}`);
  });

  it('renders SPECTATING badge when ?spectate=true is in the URL', async () => {
    setUrlSpectate(true);
    render(<MultiplayerRace />);

    await waitFor(() => {
      expect(screen.getByText('SPECTATING')).toBeInTheDocument();
    });
  });

  it('does not render keyboard controls section when spectating', async () => {
    setUrlSpectate(true);
    render(<MultiplayerRace />);

    await waitFor(() => {
      expect(screen.getByText('SPECTATING')).toBeInTheDocument();
    });

    expect(screen.queryByText(/Keyboard Controls/i)).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Start Race/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Share Lobby/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /New Track/i })).not.toBeInTheDocument();
  });

  it('renders camera controls (Follow/Free) when spectating with a game state', async () => {
    setUrlSpectate(true);
    render(<MultiplayerRace />);

    await waitFor(() => {
      expect(mockCallbacks).toBeDefined();
    });

    // Simulate a game state with one player car so playerList is non-empty
    mockCallbacks.onGameState?.({
      tick: 1,
      race_info: {
        status: 'waiting',
        start_time: null,
        countdown_remaining: 0,
        finish_time: null,
        first_finisher_time: null,
        grace_period_remaining: 0,
      },
      players: {
        'player-a': {
          car: {
            position: { x: 0, y: 0 },
            velocity: { x: 0, y: 0 },
            heading: 0,
            angular_velocity: 0,
            is_drifting: false,
            drift_angle: 0,
            nitro_charges: 3,
            nitro_active: false,
            nitro_remaining_ticks: 0,
          },
          current_checkpoint: 0,
          split_times: [],
          is_finished: false,
          finish_time: null,
          is_off_track: false,
          position: null,
          points: 0,
          dnf: false,
          is_bot: false,
          bot_name: null,
          bot_error: null,
        },
      },
    });

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Follow Car/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Free Camera/i })).toBeInTheDocument();
    });
  });

  it('connects to the WebSocket with spectate=true', async () => {
    setUrlSpectate(true);
    render(<MultiplayerRace />);

    await waitFor(() => {
      expect(mockWsInstance.connect).toHaveBeenCalled();
    });

    // 5th positional arg is `spectate`
    const args = mockWsInstance.connect.mock.calls[0];
    expect(args[4]).toBe(true);
  });

  it('does not render SPECTATING badge in normal (non-spectator) mode', async () => {
    setUrlSpectate(false);
    render(<MultiplayerRace />);

    await waitFor(() => {
      expect(mockCallbacks).toBeDefined();
    });

    expect(screen.queryByText('SPECTATING')).not.toBeInTheDocument();
  });
});
