/**
 * WebSocket client for real-time multiplayer game communication.
 */

import type { Track, InputState } from '../game/types';

// Use the current hostname to support both localhost and network access
const WS_BASE_URL = `ws://${window.location.hostname}:8000`;

export interface GameStateMessage {
  type: 'game_state';
  data: {
    tick: number;
    race_info: {
      status: string;
      start_time: number | null;
      countdown_remaining: number;
      finish_time: number | null;
      first_finisher_time: number | null;
      grace_period_remaining: number;
    };
    players: {
      [playerId: string]: {
        car: {
          position: { x: number; y: number };
          velocity: { x: number; y: number };
          heading: number;
          angular_velocity: number;
          is_drifting: boolean;
          drift_angle: number;
          nitro_charges: number;
          nitro_active: boolean;
          nitro_remaining_ticks: number;
        };
        current_checkpoint: number;
        split_times: number[];  // Elapsed time at each checkpoint
        is_finished: boolean;
        finish_time: number | null;
        is_off_track: boolean;
        position: number | null;  // Final race position (1st, 2nd, etc.)
        points: number;  // Points awarded
        dnf: boolean;  // Did Not Finish
        is_bot: boolean;  // Whether this player is a bot
        bot_name: string | null;  // Bot name if is_bot is true
        bot_error: string | null;  // Bot error message if any
      };
    };
  };
}

export interface ConnectedMessage {
  type: 'connected';
  data: {
    session_id: string;
    player_id: string;
    track: Track;
  };
}

export interface BotSubmissionResponseMessage {
  type: 'bot_submission_response';
  data: {
    success: boolean;
    bot_player_id?: string;
    bot_name?: string;
    error?: string;
  };
}

export type ServerMessage = GameStateMessage | ConnectedMessage | BotSubmissionResponseMessage;

export interface GameWebSocketCallbacks {
  onConnected?: (sessionId: string, playerId: string, track: Track) => void;
  onGameState?: (state: GameStateMessage['data']) => void;
  onBotSubmissionResponse?: (response: BotSubmissionResponseMessage['data']) => void;
  onDisconnected?: () => void;
  onError?: (error: Event) => void;
}

export class GameWebSocketClient {
  private ws: WebSocket | null = null;
  private callbacks: GameWebSocketCallbacks;
  private reconnectTimeout: number | null = null;
  private shouldReconnect: boolean = true;

  public sessionId: string | null = null;
  public playerId: string | null = null;

  constructor(callbacks: GameWebSocketCallbacks) {
    this.callbacks = callbacks;
  }

  /**
   * Connect to the game server.
   */
  connect(sessionId?: string, difficulty: string = 'medium', seed?: number): void {
    // Build WebSocket URL with query parameters
    const url = new URL(`${WS_BASE_URL}/game/ws`);
    if (sessionId) {
      url.searchParams.append('session_id', sessionId);
    }
    url.searchParams.append('difficulty', difficulty);
    if (seed !== undefined) {
      url.searchParams.append('seed', seed.toString());
    }

    this.ws = new WebSocket(url.toString());

    this.ws.onopen = () => {
      console.log('WebSocket connected');
    };

    this.ws.onmessage = (event) => {
      const message: ServerMessage = JSON.parse(event.data);
      this.handleMessage(message);
    };

    this.ws.onerror = (event) => {
      console.error('WebSocket error:', event);
      this.callbacks.onError?.(event);
    };

    this.ws.onclose = () => {
      console.log('WebSocket disconnected');
      this.ws = null;
      this.callbacks.onDisconnected?.();

      // Attempt to reconnect after a delay
      if (this.shouldReconnect) {
        this.reconnectTimeout = window.setTimeout(() => {
          console.log('Attempting to reconnect...');
          if (this.sessionId) {
            this.connect(this.sessionId, difficulty, seed);
          }
        }, 2000);
      }
    };
  }

  /**
   * Disconnect from the game server.
   */
  disconnect(): void {
    this.shouldReconnect = false;

    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }

    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }

  /**
   * Send player input to the server.
   */
  sendInput(input: InputState): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      return;
    }

    this.ws.send(JSON.stringify({
      type: 'input',
      data: {
        accelerate: input.accelerate,
        brake: input.brake,
        turn_left: input.turnLeft,
        turn_right: input.turnRight,
        nitro: input.nitro,
      },
    }));
  }

  /**
   * Send start race command to the server.
   */
  startRace(): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      return;
    }

    this.ws.send(JSON.stringify({
      type: 'start_race',
    }));
  }

  /**
   * Submit a bot to the race.
   */
  sendBot(botId: number): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      return;
    }

    this.ws.send(JSON.stringify({
      type: 'submit_bot',
      data: { bot_id: botId },
    }));
  }

  /**
   * Handle incoming message from server.
   */
  private handleMessage(message: ServerMessage): void {
    switch (message.type) {
      case 'connected':
        this.sessionId = message.data.session_id;
        this.playerId = message.data.player_id;
        console.log(`Connected as player ${this.playerId} in session ${this.sessionId}`);
        this.callbacks.onConnected?.(
          message.data.session_id,
          message.data.player_id,
          message.data.track
        );
        break;

      case 'game_state':
        this.callbacks.onGameState?.(message.data);
        break;

      case 'bot_submission_response':
        this.callbacks.onBotSubmissionResponse?.(message.data);
        break;

      default:
        console.warn('Unknown message type:', message);
    }
  }

  /**
   * Check if WebSocket is connected.
   */
  isConnected(): boolean {
    return this.ws !== null && this.ws.readyState === WebSocket.OPEN;
  }
}
