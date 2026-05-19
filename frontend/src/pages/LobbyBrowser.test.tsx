/**
 * LobbyBrowser tests for the join-existing-lobby UX (#168).
 *
 * The page already had Join/Spectate buttons; this round adds host
 * attribution per card and distinguishes the current user's own
 * lobbies ("YOUR LOBBY" badge + "Resume" button instead of "Join").
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import LobbyBrowser from './LobbyBrowser';

vi.mock('../hooks/useUsername', () => ({
  useUsername: () => ({ username: 'alice', loading: false }),
}));

vi.mock('../services', async () => {
  // Stub fetch + create. Each test sets `mockedLobbies` before render.
  return {
    fetchLobbies: vi.fn(async (status: string) => {
      return (globalThis as any).__mockedLobbies?.filter((l: any) => l.status === status) ?? [];
    }),
    createLobby: vi.fn(),
  };
});

function setLobbies(lobbies: any[]) {
  (globalThis as any).__mockedLobbies = lobbies;
}

function renderBrowser() {
  return render(
    <MemoryRouter>
      <LobbyBrowser />
    </MemoryRouter>,
  );
}

const baseLobby = (overrides: Partial<any> = {}) => ({
  lobby_id: 'lobby-1',
  join_code: 'TEST-CODE',
  name: 'Test Lobby',
  host_player_id: 'someone-else',
  creator_player_id: 'someone-else',
  member_count: 1,
  max_players: 4,
  status: 'waiting',
  created_at: 0,
  spectator_count: 0,
  game_session_id: null,
  ...overrides,
});

describe('LobbyBrowser — join existing lobby (#168)', () => {
  beforeEach(() => {
    (globalThis as any).__mockedLobbies = [];
  });

  it('shows the creator name on every lobby card', async () => {
    setLobbies([
      baseLobby({ name: 'BobsRace', host_player_id: 'bob', creator_player_id: 'bob' }),
      baseLobby({ lobby_id: 'lobby-2', name: 'CarolsRace',
                  host_player_id: 'carol', creator_player_id: 'carol' }),
    ]);

    renderBrowser();

    await waitFor(() => expect(screen.getByText('BobsRace')).toBeInTheDocument());
    // Creator name appears inside a span next to "Created by"; match
    // the text node that holds both via a flexible function matcher.
    const hasCreatorText = (name: string) =>
      (_content: string, node: Element | null) =>
        node?.textContent === `Created by ${name}`;
    expect(screen.getByText(hasCreatorText('bob'))).toBeInTheDocument();
    expect(screen.getByText(hasCreatorText('carol'))).toBeInTheDocument();
  });

  it('badges a lobby as the user\'s own based on creator_player_id, NOT host_player_id', async () => {
    // Regression for the host-transferred-to-bot case: when alice creates
    // a lobby, adds bots, and leaves, host_player_id transfers to a bot
    // (e.g. "llm-alice-2"). The card must still show "YOUR LOBBY" for
    // alice because creator_player_id is stable.
    setLobbies([
      baseLobby({
        host_player_id: 'llm-alice-2',  // transferred to an LLM bot
        creator_player_id: 'alice',     // alice still owns it
        name: 'AlicesTrashedLobby',
      }),
    ]);

    renderBrowser();

    await waitFor(() => expect(screen.getByText('AlicesTrashedLobby')).toBeInTheDocument());
    expect(screen.getByTestId('your-lobby-badge')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Resume/i })).toBeInTheDocument();
  });

  it('shows "YOUR LOBBY" badge and Resume button on the current user\'s own lobbies', async () => {
    setLobbies([
      baseLobby({
        host_player_id: 'alice',
        creator_player_id: 'alice',
        name: 'AlicesRace',
      }),
    ]);

    renderBrowser();

    await waitFor(() => expect(screen.getByText('AlicesRace')).toBeInTheDocument());
    expect(screen.getByTestId('your-lobby-badge')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Resume/i })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /^Join$/i })).toBeNull();
  });

  it('shows a Join button for a lobby owned by someone else (WAITING status)', async () => {
    setLobbies([
      baseLobby({ host_player_id: 'bob', name: 'BobsRace' }),
    ]);

    renderBrowser();

    await waitFor(() => expect(screen.getByText('BobsRace')).toBeInTheDocument());
    expect(screen.getByRole('button', { name: /^Join$/i })).toBeInTheDocument();
    expect(screen.queryByTestId('your-lobby-badge')).toBeNull();
  });

  it('shows Full when a non-own lobby is at max capacity', async () => {
    setLobbies([
      baseLobby({ host_player_id: 'bob', name: 'BobsRace', member_count: 4, max_players: 4 }),
    ]);

    renderBrowser();

    await waitFor(() => expect(screen.getByText('BobsRace')).toBeInTheDocument());
    expect(screen.getByRole('button', { name: /^Full$/i })).toBeInTheDocument();
  });

  it('shows only Spectate for racing lobbies (no Join)', async () => {
    setLobbies([
      baseLobby({
        host_player_id: 'bob',
        name: 'BobsRace',
        status: 'racing',
        game_session_id: 'sess-1',
      }),
    ]);

    renderBrowser();

    await waitFor(() => expect(screen.getByText('BobsRace')).toBeInTheDocument());
    expect(screen.queryByRole('button', { name: /^Join$/i })).toBeNull();
    expect(screen.queryByRole('button', { name: /^Resume$/i })).toBeNull();
    expect(screen.getByRole('button', { name: /Spectate/i })).toBeInTheDocument();
  });
});
