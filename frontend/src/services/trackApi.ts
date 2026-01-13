/**
 * API service for track generation.
 */

import type { Track } from '../game/types';
import { getApiBaseUrl } from '../config';

const API_BASE_URL = getApiBaseUrl();

export interface GenerateTrackParams {
  difficulty?: 'easy' | 'medium' | 'hard';
  seed?: number;
}

/**
 * Generate a new track from the backend API.
 */
export async function generateTrack(params: GenerateTrackParams = {}): Promise<Track> {
  const { difficulty = 'medium', seed } = params;

  const url = new URL(`${API_BASE_URL}/tracks/generate`);
  url.searchParams.append('difficulty', difficulty);
  if (seed !== undefined) {
    url.searchParams.append('seed', seed.toString());
  }

  const response = await fetch(url.toString(), {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    throw new Error(`Failed to generate track: ${response.statusText}`);
  }

  const track: Track = await response.json();
  return track;
}
