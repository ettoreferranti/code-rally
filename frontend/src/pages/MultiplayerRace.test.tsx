/**
 * Tests for bot submission functionality in MultiplayerRace component.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { userEvent } from '@testing-library/user-event';
import MultiplayerRace from './MultiplayerRace';
import * as botApi from '../services/botApi';
import { GameWebSocketClient } from '../services/gameWebSocket';

// Mock the bot API
vi.mock('../services/botApi');

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

describe('MultiplayerRace - Bot Submission', () => {
  let mockWsInstance: any;
  let mockCallbacks: any;

  beforeEach(() => {
    // Reset mocks
    vi.clearAllMocks();

    // Capture WebSocket callbacks
    vi.mocked(GameWebSocketClient).mockImplementation(function(this: any, callbacks: any) {
      mockCallbacks = callbacks;
      mockWsInstance = this;

      this.callbacks = callbacks;
      this.connect = vi.fn((sessionId, difficulty, seed) => {
        // Simulate successful connection
        setTimeout(() => {
          callbacks.onConnected?.('test-session-id', 'test-player-id', {
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
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renders bot selection dropdown when user has bots', async () => {
    // Mock API to return test bots
    vi.mocked(botApi.getUserBots).mockResolvedValue([
      { id: 1, name: 'SpeedBot', created_at: '2024-01-01', updated_at: '2024-01-01' },
      { id: 2, name: 'DriftBot', created_at: '2024-01-02', updated_at: '2024-01-02' },
    ]);

    render(<MultiplayerRace />);

    // Wait for bots to load
    await waitFor(() => {
      expect(botApi.getUserBots).toHaveBeenCalledWith('testuser');
    });

    // Check dropdown exists with bot options
    await waitFor(() => {
      const dropdown = screen.getByRole('combobox');
      expect(dropdown).toBeInTheDocument();
    });

    // Verify bot names are in the dropdown
    expect(screen.getByRole('option', { name: 'SpeedBot' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'DriftBot' })).toBeInTheDocument();
  });

  it('renders Submit Bot button when user has bots', async () => {
    vi.mocked(botApi.getUserBots).mockResolvedValue([
      { id: 1, name: 'SpeedBot', created_at: '2024-01-01', updated_at: '2024-01-01' },
    ]);

    render(<MultiplayerRace />);

    await waitFor(() => {
      const submitButton = screen.getByRole('button', { name: /Submit Bot/i });
      expect(submitButton).toBeInTheDocument();
    });
  });

  it('does not render bot controls when user has no bots', async () => {
    vi.mocked(botApi.getUserBots).mockResolvedValue([]);

    render(<MultiplayerRace />);

    await waitFor(() => {
      expect(botApi.getUserBots).toHaveBeenCalledWith('testuser');
    });

    // Should not render dropdown or submit button
    expect(screen.queryByRole('combobox')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Submit Bot/i })).not.toBeInTheDocument();
  });

  it('sends bot submission via WebSocket when Submit Bot is clicked', async () => {
    const user = userEvent.setup();

    vi.mocked(botApi.getUserBots).mockResolvedValue([
      { id: 1, name: 'SpeedBot', created_at: '2024-01-01', updated_at: '2024-01-01' },
      { id: 2, name: 'DriftBot', created_at: '2024-01-02', updated_at: '2024-01-02' },
    ]);

    render(<MultiplayerRace />);

    // Wait for connection
    await waitFor(() => {
      expect(screen.getByText(/Session:/)).toBeInTheDocument();
    });

    // Wait for bots to load
    await waitFor(() => {
      expect(screen.getByRole('combobox')).toBeInTheDocument();
    });

    // Select a bot from dropdown
    const dropdown = screen.getByRole('combobox');
    await user.selectOptions(dropdown, '2'); // Select DriftBot (id=2)

    // Click Submit Bot
    const submitButton = screen.getByRole('button', { name: /Submit Bot/i });
    await user.click(submitButton);

    // Verify WebSocket sendBot was called with correct bot ID
    expect(mockWsInstance.sendBot).toHaveBeenCalledWith(2);
  });

  it('displays success message when bot submission succeeds', async () => {
    vi.mocked(botApi.getUserBots).mockResolvedValue([
      { id: 1, name: 'SpeedBot', created_at: '2024-01-01', updated_at: '2024-01-01' },
    ]);

    render(<MultiplayerRace />);

    // Wait for connection
    await waitFor(() => {
      expect(mockCallbacks).toBeDefined();
    });

    // Simulate successful bot submission response
    mockCallbacks.onBotSubmissionResponse?.({
      success: true,
      bot_player_id: 'bot-testuser-SpeedBot',
      bot_name: 'SpeedBot',
    });

    // Verify success message is displayed
    await waitFor(() => {
      expect(screen.getByText(/✓ Bot "SpeedBot" submitted!/)).toBeInTheDocument();
    });
  });

  it('displays error message when bot submission fails', async () => {
    vi.mocked(botApi.getUserBots).mockResolvedValue([
      { id: 1, name: 'SpeedBot', created_at: '2024-01-01', updated_at: '2024-01-01' },
    ]);

    render(<MultiplayerRace />);

    // Wait for connection
    await waitFor(() => {
      expect(mockCallbacks).toBeDefined();
    });

    // Simulate failed bot submission response
    mockCallbacks.onBotSubmissionResponse?.({
      success: false,
      error: 'Bot not found',
    });

    // Verify error message is displayed
    await waitFor(() => {
      expect(screen.getByText(/✗ Error: Bot not found/)).toBeInTheDocument();
    });
  });

  it('disables Submit Bot button during countdown', async () => {
    vi.mocked(botApi.getUserBots).mockResolvedValue([
      { id: 1, name: 'SpeedBot', created_at: '2024-01-01', updated_at: '2024-01-01' },
    ]);

    render(<MultiplayerRace />);

    // Wait for connection
    await waitFor(() => {
      expect(mockCallbacks).toBeDefined();
    });

    // Simulate game state with countdown status
    mockCallbacks.onGameState?.({
      tick: 10,
      race_info: {
        status: 'countdown',
        start_time: null,
        countdown_remaining: 3,
        finish_time: null,
        first_finisher_time: null,
        grace_period_remaining: 0,
      },
      players: {
        'test-player-id': {
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

    // Wait for Submit Bot button to appear
    await waitFor(() => {
      const submitButton = screen.getByRole('button', { name: /Submit Bot/i });
      expect(submitButton).toBeDisabled();
    });
  });

  it('disables Submit Bot button when race is finished', async () => {
    vi.mocked(botApi.getUserBots).mockResolvedValue([
      { id: 1, name: 'SpeedBot', created_at: '2024-01-01', updated_at: '2024-01-01' },
    ]);

    render(<MultiplayerRace />);

    // Wait for connection
    await waitFor(() => {
      expect(mockCallbacks).toBeDefined();
    });

    // Simulate game state with finished status
    mockCallbacks.onGameState?.({
      tick: 1000,
      race_info: {
        status: 'finished',
        start_time: 100,
        countdown_remaining: 0,
        finish_time: 500,
        first_finisher_time: 500,
        grace_period_remaining: 0,
      },
      players: {
        'test-player-id': {
          car: {
            position: { x: 100, y: 100 },
            velocity: { x: 0, y: 0 },
            heading: 0,
            angular_velocity: 0,
            is_drifting: false,
            drift_angle: 0,
            nitro_charges: 0,
            nitro_active: false,
            nitro_remaining_ticks: 0,
          },
          current_checkpoint: 5,
          split_times: [10, 20, 30, 40, 50],
          is_finished: true,
          finish_time: 500,
          is_off_track: false,
          position: 1,
          points: 100,
          dnf: false,
          is_bot: false,
          bot_name: null,
          bot_error: null,
        },
      },
    });

    // Wait for Submit Bot button to appear
    await waitFor(() => {
      const submitButton = screen.getByRole('button', { name: /Submit Bot/i });
      expect(submitButton).toBeDisabled();
    });
  });

  it('allows bot submission when race is waiting or racing', async () => {
    const user = userEvent.setup();

    vi.mocked(botApi.getUserBots).mockResolvedValue([
      { id: 1, name: 'SpeedBot', created_at: '2024-01-01', updated_at: '2024-01-01' },
    ]);

    render(<MultiplayerRace />);

    // Wait for connection
    await waitFor(() => {
      expect(mockCallbacks).toBeDefined();
    });

    // Simulate game state with waiting status
    mockCallbacks.onGameState?.({
      tick: 0,
      race_info: {
        status: 'waiting',
        start_time: null,
        countdown_remaining: 0,
        finish_time: null,
        first_finisher_time: null,
        grace_period_remaining: 0,
      },
      players: {
        'test-player-id': {
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

    // Wait for Submit Bot button to be enabled
    await waitFor(() => {
      const submitButton = screen.getByRole('button', { name: /Submit Bot/i });
      expect(submitButton).not.toBeDisabled();
    });
  });
});
