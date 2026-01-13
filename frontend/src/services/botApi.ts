/**
 * API service for bot and user management.
 *
 * Provides CRUD operations for bots and user registration.
 */

import { getApiBaseUrl } from '../config';

const API_BASE_URL = getApiBaseUrl();

// TypeScript interfaces matching backend models
export interface User {
  id: number;
  username: string;
  created_at: string;
  updated_at: string;
}

export interface Bot {
  id: number;
  name: string;
  code: string;
  user_id: number;
  created_at: string;
  updated_at: string;
}

export interface BotListItem {
  id: number;
  name: string;
  user_id: number;
  created_at: string;
  updated_at: string;
}

export interface CreateBotRequest {
  name: string;
  code: string;
}

export interface UpdateBotRequest {
  name?: string;
  code?: string;
}

export interface TemplateInfo {
  id: string;
  name: string;
  difficulty: number;
  description: string;
  features: string[];
}

export interface TemplateCodeResponse {
  id: string;
  name: string;
  code: string;
}

/**
 * Get all users.
 *
 * @returns Array of all users
 */
export async function getAllUsers(): Promise<User[]> {
  const response = await fetch(`${API_BASE_URL}/users`);

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || `Failed to get users: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Register a new user or get existing user (idempotent).
 *
 * @param username - Username to register (3-50 chars, alphanumeric + dash/underscore)
 * @returns User object
 */
export async function registerUser(username: string): Promise<User> {
  const response = await fetch(`${API_BASE_URL}/users/register`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ username }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || `Failed to register user: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Get user by username.
 *
 * @param username - Username to lookup
 * @returns User object
 */
export async function getUser(username: string): Promise<User> {
  const response = await fetch(`${API_BASE_URL}/users/${username}`);

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || `Failed to get user: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Delete a user and all their bots.
 *
 * @param username - Username to delete
 */
export async function deleteUser(username: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/users/${username}`, {
    method: 'DELETE',
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || `Failed to delete user: ${response.statusText}`);
  }
}

/**
 * List all bots for a user (ordered by most recently updated).
 *
 * @param username - Username to lookup bots for
 * @returns Array of bot list items (without code for performance)
 */
export async function getUserBots(username: string): Promise<BotListItem[]> {
  const response = await fetch(`${API_BASE_URL}/bots/users/${username}/bots`);

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || `Failed to get user bots: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Get a specific bot by ID (includes code).
 *
 * @param botId - Bot ID to lookup
 * @returns Bot object with code
 */
export async function getBot(botId: number): Promise<Bot> {
  const response = await fetch(`${API_BASE_URL}/bots/${botId}`);

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || `Failed to get bot: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Create a new bot for a user.
 *
 * Validates code with RestrictedPython sandbox before saving.
 *
 * @param username - Owner username
 * @param request - Bot creation request (name and code)
 * @returns Created bot object
 */
export async function createBot(username: string, request: CreateBotRequest): Promise<Bot> {
  const response = await fetch(`${API_BASE_URL}/bots/users/${username}/bots`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || `Failed to create bot: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Update an existing bot.
 *
 * Can update name, code, or both. Validates code if provided.
 *
 * @param botId - Bot ID to update
 * @param request - Update request with optional name and/or code
 * @returns Updated bot object
 */
export async function updateBot(botId: number, request: UpdateBotRequest): Promise<Bot> {
  const response = await fetch(`${API_BASE_URL}/bots/${botId}`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || `Failed to update bot: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Delete a bot.
 *
 * @param botId - Bot ID to delete
 */
export async function deleteBot(botId: number): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/bots/${botId}`, {
    method: 'DELETE',
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || `Failed to delete bot: ${response.statusText}`);
  }
}

/**
 * Get list of available bot templates.
 *
 * @returns Array of template metadata (without code)
 */
export async function getTemplates(): Promise<TemplateInfo[]> {
  const response = await fetch(`${API_BASE_URL}/bots/templates`);

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || `Failed to get templates: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Get source code for a specific template.
 *
 * @param templateId - Template identifier (e.g., "simple_follower")
 * @returns Template code and metadata
 */
export async function getTemplate(templateId: string): Promise<TemplateCodeResponse> {
  const response = await fetch(`${API_BASE_URL}/bots/templates/${templateId}`);

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || `Failed to get template: ${response.statusText}`);
  }

  return response.json();
}
