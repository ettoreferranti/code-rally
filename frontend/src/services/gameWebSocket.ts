/**
 * WebSocket client for real-time multiplayer game communication.
 */

import type { Track, InputState } from '../game/types';

const WS_BASE_URL = 'ws://localhost:8000';

export interface GameStateMessage {
  type: 'game_state';
  data: {
    tick: number;
    race_info: {
      status: string;
      start_time: number | null;
      countdown_remaining: number;
      finish_time: number | null;
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
        };
        current_checkpoint: number;
        is_finished: boolean;
        finish_time: number | null;
        is_off_track: boolean;
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

export type ServerMessage = GameStateMessage | ConnectedMessage;

export interface GameWebSocketCallbacks {
  onConnected?: (sessionId: string, playerId: string, track: Track) => void;
  onGameState?: (state: GameStateMessage['data']) => void;
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
