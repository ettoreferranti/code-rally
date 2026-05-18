/**
 * LobbyWaitingRoom tests for the "Add LLM Bot" feature (issue #157).
 *
 * Mocks the WebSocket constructor so we can drive the lobby into the
 * host view and observe the message the UI sends when the host clicks
 * "Add LLM Bot".
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, act } from '@testing-library/react';
import { userEvent } from '@testing-library/user-event';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import LobbyWaitingRoom from './LobbyWaitingRoom';

vi.mock('../hooks/useUsername', () => ({
  useUsername: () => ({ username: 'alice', loading: false }),
}));

/** A minimal WebSocket stub we can install on globalThis. */
class FakeWebSocket {
  static OPEN = 1;
  static CLOSED = 3;
  static CLOSING = 2;
  static CONNECTING = 0;

  static lastInstance: FakeWebSocket | null = null;

  readyState = FakeWebSocket.OPEN;
  sent: string[] = [];
  onopen: (() => void) | null = null;
  onmessage: ((e: { data: string }) => void) | null = null;
  onerror: (() => void) | null = null;
  onclose: (() => void) | null = null;

  constructor(public url: string) {
    FakeWebSocket.lastInstance = this;
    setTimeout(() => this.onopen?.(), 0);
  }

  send(data: string) {
    this.sent.push(data);
  }

  close() {
    this.readyState = FakeWebSocket.CLOSED;
    this.onclose?.();
  }
}

function renderLobby() {
  return render(
    <MemoryRouter initialEntries={['/lobbies/test-lobby-id']}>
      <Routes>
        <Route path="/lobbies/:lobbyId" element={<LobbyWaitingRoom />} />
      </Routes>
    </MemoryRouter>,
  );
}

function pushLobbyJoined(state: any) {
  const ws = FakeWebSocket.lastInstance!;
  ws.onmessage?.({
    data: JSON.stringify({
      type: 'lobby_joined',
      data: {
        player_id: 'alice',
        lobby: state,
      },
    }),
  });
}

function pushLobbyStateUpdate(state: any) {
  const ws = FakeWebSocket.lastInstance!;
  ws.onmessage?.({
    data: JSON.stringify({
      type: 'lobby_state',
      data: state,
    }),
  });
}

const baseLobby = {
  lobby_id: 'test-lobby-id',
  join_code: 'TEST-CODE',
  name: 'Test Lobby',
  host_player_id: 'alice',
  settings: {
    track_difficulty: 'easy',
    track_seed: null,
    max_players: 4,
    finish_grace_period: 30,
  },
  status: 'waiting',
  created_at: 0,
  game_session_id: null,
  spectator_count: 0,
  members: [
    {
      player_id: 'alice',
      username: 'alice',
      driver_kind: 'human',
      is_bot: false,
      bot_id: null,
      ready: false,
    },
  ],
};

describe('LobbyWaitingRoom — Add LLM Bot', () => {
  beforeEach(() => {
    FakeWebSocket.lastInstance = null;
    (globalThis as any).WebSocket = FakeWebSocket;
  });

  it('shows the Add LLM Bot button when the user is the host', async () => {
    renderLobby();
    await waitFor(() => expect(FakeWebSocket.lastInstance).toBeTruthy());
    act(() => pushLobbyJoined(baseLobby));

    expect(await screen.findByTestId('add-llm-bot-button')).toBeInTheDocument();
    expect(screen.getByTestId('llm-model-input')).toBeInTheDocument();
  });

  it('sends add_llm_bot_to_lobby with no model_path when the field is empty', async () => {
    renderLobby();
    await waitFor(() => expect(FakeWebSocket.lastInstance).toBeTruthy());
    act(() => pushLobbyJoined(baseLobby));

    const button = await screen.findByTestId('add-llm-bot-button');
    await userEvent.click(button);

    const sent = FakeWebSocket.lastInstance!.sent.map((s) => JSON.parse(s));
    const addMsg = sent.find((m) => m.type === 'add_llm_bot_to_lobby');
    expect(addMsg).toBeTruthy();
    expect(addMsg.data).toEqual({});
  });

  it('sends model_path when the input has a value', async () => {
    renderLobby();
    await waitFor(() => expect(FakeWebSocket.lastInstance).toBeTruthy());
    act(() => pushLobbyJoined(baseLobby));

    const input = await screen.findByTestId('llm-model-input');
    await userEvent.type(input, 'mlx-community/Qwen2.5-7B-Instruct-4bit');
    await userEvent.click(screen.getByTestId('add-llm-bot-button'));

    const addMsg = FakeWebSocket.lastInstance!.sent
      .map((s) => JSON.parse(s))
      .find((m) => m.type === 'add_llm_bot_to_lobby');
    expect(addMsg.data).toEqual({
      model_path: 'mlx-community/Qwen2.5-7B-Instruct-4bit',
    });
  });

  it('renders an LLM badge for members with driver_kind="llm_bot"', async () => {
    renderLobby();
    await waitFor(() => expect(FakeWebSocket.lastInstance).toBeTruthy());

    const lobbyWithLlm = {
      ...baseLobby,
      members: [
        ...baseLobby.members,
        {
          player_id: 'llm-bot-1-abcdef',
          username: 'LLM Bot 1',
          driver_kind: 'llm_bot',
          is_bot: true,
          bot_id: null,
          ready: true,
          llm_model_path: null,
        },
      ],
    };
    act(() => pushLobbyJoined(lobbyWithLlm));

    expect(await screen.findByTestId('llm-bot-badge')).toBeInTheDocument();
  });

  it('updates roster to show LLM badge when a lobby_state update arrives', async () => {
    renderLobby();
    await waitFor(() => expect(FakeWebSocket.lastInstance).toBeTruthy());
    act(() => pushLobbyJoined(baseLobby));

    // No LLM bot initially.
    expect(screen.queryByTestId('llm-bot-badge')).toBeNull();

    const updated = {
      ...baseLobby,
      members: [
        ...baseLobby.members,
        {
          player_id: 'llm-bot-1-abcdef',
          username: 'LLM Bot 1',
          driver_kind: 'llm_bot',
          is_bot: true,
          bot_id: null,
          ready: true,
          llm_model_path: 'mlx-community/Qwen2.5-7B-Instruct-4bit',
        },
      ],
    };
    act(() => pushLobbyStateUpdate(updated));

    const badge = await screen.findByTestId('llm-bot-badge');
    expect(badge).toBeInTheDocument();
    expect(badge.getAttribute('title')).toContain('Qwen2.5-7B');
  });
});
