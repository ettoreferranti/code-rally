/**
 * LobbyWaitingRoom tests for the unified "Add bot" picker.
 *
 * Mocks the WebSocket constructor (so we can observe outbound messages)
 * and the bot library fetch (so the dropdown is populated).
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, act } from '@testing-library/react';
import { userEvent } from '@testing-library/user-event';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import LobbyWaitingRoom from './LobbyWaitingRoom';

vi.mock('../hooks/useUsername', () => ({
  useUsername: () => ({ username: 'alice', loading: false }),
}));

// Stub the user's bot library so the unified dropdown has options.
vi.mock('../services/botApi', () => ({
  getUserBots: async () => [
    {
      id: 11,
      name: 'SpeedBot',
      kind: 'python',
      model_path: null,
      user_id: 1,
      created_at: '',
      updated_at: '',
    },
    {
      id: 22,
      name: 'AggressiveQwen',
      kind: 'llm',
      model_path: 'mlx-community/Qwen2.5-1.5B-Instruct-4bit',
      user_id: 1,
      created_at: '',
      updated_at: '',
    },
  ],
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
  url: string;

  constructor(url: string) {
    this.url = url;
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

describe('LobbyWaitingRoom — unified add-bot', () => {
  beforeEach(() => {
    FakeWebSocket.lastInstance = null;
    (globalThis as any).WebSocket = FakeWebSocket;
  });

  it('shows the unified bot picker when the user is the host', async () => {
    renderLobby();
    await waitFor(() => expect(FakeWebSocket.lastInstance).toBeTruthy());
    act(() => pushLobbyJoined(baseLobby));

    expect(await screen.findByTestId('add-bot-select')).toBeInTheDocument();
    expect(screen.getByTestId('add-bot-button')).toBeInTheDocument();
  });

  it('lists both Python and LLM bots in the picker with kind badges in the label', async () => {
    renderLobby();
    await waitFor(() => expect(FakeWebSocket.lastInstance).toBeTruthy());
    act(() => pushLobbyJoined(baseLobby));

    const select = (await screen.findByTestId('add-bot-select')) as HTMLSelectElement;
    const optionTexts = Array.from(select.options).map((o) => o.textContent ?? '');
    expect(optionTexts.some((t) => t.includes('[PY]') && t.includes('SpeedBot'))).toBe(true);
    expect(optionTexts.some((t) => t.includes('[LLM]') && t.includes('AggressiveQwen'))).toBe(true);
  });

  it('sends add_bot_to_lobby with bot_id when "Add to lobby" is clicked', async () => {
    renderLobby();
    await waitFor(() => expect(FakeWebSocket.lastInstance).toBeTruthy());
    act(() => pushLobbyJoined(baseLobby));

    const select = (await screen.findByTestId('add-bot-select')) as HTMLSelectElement;
    await userEvent.selectOptions(select, '22');  // The LLM bot
    await userEvent.click(screen.getByTestId('add-bot-button'));

    const addMsg = FakeWebSocket.lastInstance!.sent
      .map((s) => JSON.parse(s))
      .find((m) => m.type === 'add_bot_to_lobby');
    expect(addMsg).toBeTruthy();
    expect(addMsg.data).toEqual({ bot_id: 22 });
  });

  it('renders an LLM badge for members with driver_kind="llm_bot"', async () => {
    renderLobby();
    await waitFor(() => expect(FakeWebSocket.lastInstance).toBeTruthy());

    const lobbyWithLlm = {
      ...baseLobby,
      members: [
        ...baseLobby.members,
        {
          player_id: 'llm-alice-22',
          username: 'alice/AggressiveQwen',
          driver_kind: 'llm_bot',
          is_bot: true,
          bot_id: 22,
          ready: true,
          llm_model_path: 'mlx-community/Qwen2.5-1.5B-Instruct-4bit',
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

    expect(screen.queryByTestId('llm-bot-badge')).toBeNull();

    const updated = {
      ...baseLobby,
      members: [
        ...baseLobby.members,
        {
          player_id: 'llm-alice-22',
          username: 'alice/AggressiveQwen',
          driver_kind: 'llm_bot',
          is_bot: true,
          bot_id: 22,
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
