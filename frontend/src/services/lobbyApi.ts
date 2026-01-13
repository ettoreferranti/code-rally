/**
 * Lobby API client for REST endpoints.
 *
 * Provides functions to interact with the lobby system backend.
 */

import { getApiBaseUrl } from '../config';

const API_BASE_URL = getApiBaseUrl();

export interface LobbySettings {
  track_difficulty: string;
  track_seed: number | null;
  max_players: number;
  finish_grace_period: number;
}

export interface LobbyMember {
  player_id: string;
  username: string | null;
  is_bot: boolean;
  bot_id: number | null;
  ready: boolean;
}

export interface LobbyListItem {
  lobby_id: string;
  join_code: string;
  name: string;
  host_player_id: string;
  member_count: number;
  max_players: number;
  status: string;
  created_at: number;
}

export interface Lobby {
  lobby_id: string;
  join_code: string;
  name: string;
  host_player_id: string;
  settings: LobbySettings;
  members: LobbyMember[];
  status: string;
  created_at: number;
  game_session_id: string | null;
}

export interface CreateLobbyRequest {
  name: string;
  host_player_id: string;
  track_difficulty?: string;
  track_seed?: number;
  max_players?: number;
}

export interface UpdateSettingsRequest {
  track_difficulty?: string;
  track_seed?: number;
  max_players?: number;
}

/**
 * Fetch all lobbies, optionally filtered by status.
 */
export async function fetchLobbies(status?: string): Promise<LobbyListItem[]> {
  const url = new URL(`${API_BASE_URL}/lobbies`);
  if (status) {
    url.searchParams.set('status', status);
  }

  const response = await fetch(url.toString());
  if (!response.ok) {
    throw new Error(`Failed to fetch lobbies: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Fetch a specific lobby by ID.
 */
export async function fetchLobby(lobbyId: string): Promise<Lobby> {
  const response = await fetch(`${API_BASE_URL}/lobbies/${lobbyId}`);
  if (!response.ok) {
    throw new Error(`Failed to fetch lobby: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Fetch a specific lobby by join code.
 */
export async function fetchLobbyByCode(joinCode: string): Promise<Lobby> {
  const response = await fetch(`${API_BASE_URL}/lobbies/join/${joinCode}`);
  if (!response.ok) {
    throw new Error(`Failed to fetch lobby: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Create a new lobby.
 */
export async function createLobby(request: CreateLobbyRequest): Promise<Lobby> {
  const response = await fetch(`${API_BASE_URL}/lobbies`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    throw new Error(`Failed to create lobby: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Update lobby settings (host only).
 */
export async function updateLobbySettings(
  lobbyId: string,
  playerId: string,
  settings: UpdateSettingsRequest
): Promise<Lobby> {
  const url = new URL(`${API_BASE_URL}/lobbies/${lobbyId}/settings`);
  url.searchParams.set('player_id', playerId);

  const response = await fetch(url.toString(), {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(settings),
  });

  if (!response.ok) {
    throw new Error(`Failed to update settings: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Disband a lobby (host only).
 */
export async function disbandLobby(lobbyId: string, playerId: string): Promise<void> {
  const url = new URL(`${API_BASE_URL}/lobbies/${lobbyId}`);
  url.searchParams.set('player_id', playerId);

  const response = await fetch(url.toString(), {
    method: 'DELETE',
  });

  if (!response.ok) {
    throw new Error(`Failed to disband lobby: ${response.statusText}`);
  }
}
