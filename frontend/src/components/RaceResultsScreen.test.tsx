/**
 * Tests for RaceResultsScreen.
 *
 * The post-race results table is the place where multiple LLM bots from
 * the same owner (often with the same name) become impossible to tell
 * apart. The model badge ("Qwen 7B", "Qwen 1.5B", etc.) lives next to
 * each player name so the table stays disambiguatable.
 */

import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { RaceResultsScreen } from './RaceResultsScreen';
import type { PlayerResult } from '../game/types';

const NOOP = () => {};

const _result = (overrides: Partial<PlayerResult> = {}): PlayerResult => ({
  playerId: 'p',
  position: 1,
  finishTime: 60,
  points: 5,
  dnf: false,
  ...overrides,
});

describe('RaceResultsScreen — model badge', () => {
  it('shows a model label next to LLM-driven rows', () => {
    render(
      <RaceResultsScreen
        results={[
          _result({
            playerId: 'llm-1',
            playerName: 'Speedy',
            llmModelLabel: 'Qwen 7B',
            position: 1,
          }),
        ]}
        currentPlayerId="other"
        onClose={NOOP}
      />
    );
    const badge = screen.getByTestId('result-model-label');
    expect(badge.textContent).toBe('Qwen 7B');
  });

  it('omits the badge for human / Python-bot rows (no llmModelLabel)', () => {
    render(
      <RaceResultsScreen
        results={[
          _result({
            playerId: 'human-1',
            playerName: 'Alice',
            position: 1,
          }),
        ]}
        currentPlayerId="other"
        onClose={NOOP}
      />
    );
    expect(screen.queryByTestId('result-model-label')).toBeNull();
  });

  it('renders different badges for two LLM bots with the same name', () => {
    // The whole reason this badge exists: tell apart two bots that
    // share a player name (often the case when the same user adds
    // multiple LLM bots from their Tinker library).
    render(
      <RaceResultsScreen
        results={[
          _result({
            playerId: 'llm-7b',
            playerName: 'MyLLM',
            llmModelLabel: 'Qwen 7B',
            position: 1,
          }),
          _result({
            playerId: 'llm-3b',
            playerName: 'MyLLM',
            llmModelLabel: 'Qwen 3B',
            position: 2,
          }),
        ]}
        currentPlayerId="other"
        onClose={NOOP}
      />
    );
    const badges = screen.getAllByTestId('result-model-label');
    expect(badges).toHaveLength(2);
    const texts = badges.map((b) => b.textContent);
    expect(texts).toContain('Qwen 7B');
    expect(texts).toContain('Qwen 3B');
  });
});
