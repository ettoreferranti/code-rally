/**
 * Tests for AgentThoughtBubble (issue #156).
 *
 * The bubble surfaces an LLM-driven car's latest intent above the car.
 * It must:
 *   - render speed + aggression hint when a fresh intent is supplied,
 *   - fade to "stale" styling when the intent timestamp is >2s old,
 *   - render nothing when the intent is undefined.
 */

import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { AgentThoughtBubble } from './AgentThoughtBubble';

const NOW = 1_700_000_000;  // arbitrary "current" server time in seconds

describe('AgentThoughtBubble', () => {
  it('renders speed and aggression hint when intent is fresh', () => {
    render(
      <AgentThoughtBubble
        intent={{
          target_speed_kmh: 85,
          racing_line_offset_m: 0,
          aggression: 0.8,
          ts: NOW,
        }}
        position={{ x: 100, y: 200 }}
        now={NOW}
      />
    );

    expect(screen.getByText(/85 km\/h/)).toBeInTheDocument();
    expect(screen.getByText(/aggressive/)).toBeInTheDocument();
  });

  it('maps aggression value to the right hint', () => {
    const { rerender } = render(
      <AgentThoughtBubble
        intent={{ target_speed_kmh: 50, racing_line_offset_m: 0, aggression: 0.1, ts: NOW }}
        position={{ x: 0, y: 0 }}
        now={NOW}
      />
    );
    expect(screen.getByText(/cautious/)).toBeInTheDocument();

    rerender(
      <AgentThoughtBubble
        intent={{ target_speed_kmh: 50, racing_line_offset_m: 0, aggression: 0.5, ts: NOW }}
        position={{ x: 0, y: 0 }}
        now={NOW}
      />
    );
    expect(screen.getByText(/steady/)).toBeInTheDocument();

    rerender(
      <AgentThoughtBubble
        intent={{ target_speed_kmh: 50, racing_line_offset_m: 0, aggression: 0.9, ts: NOW }}
        position={{ x: 0, y: 0 }}
        now={NOW}
      />
    );
    expect(screen.getByText(/aggressive/)).toBeInTheDocument();
  });

  it('applies stale styling when intent is older than 2 seconds', () => {
    render(
      <AgentThoughtBubble
        intent={{
          target_speed_kmh: 60,
          racing_line_offset_m: 0,
          aggression: 0.5,
          ts: NOW - 5,
        }}
        position={{ x: 100, y: 200 }}
        now={NOW}
      />
    );

    const bubble = screen.getByTestId('agent-thought-bubble');
    expect(bubble).toHaveClass('opacity-50');
  });

  it('renders at full opacity when intent is within 2 seconds', () => {
    render(
      <AgentThoughtBubble
        intent={{
          target_speed_kmh: 60,
          racing_line_offset_m: 0,
          aggression: 0.5,
          ts: NOW - 1,
        }}
        position={{ x: 100, y: 200 }}
        now={NOW}
      />
    );

    const bubble = screen.getByTestId('agent-thought-bubble');
    expect(bubble).not.toHaveClass('opacity-50');
  });

  it('renders nothing when intent is undefined', () => {
    const { container } = render(
      <AgentThoughtBubble
        intent={undefined}
        position={{ x: 100, y: 200 }}
        now={NOW}
      />
    );

    expect(container.firstChild).toBeNull();
  });

  it('positions itself using the provided screen coordinates', () => {
    render(
      <AgentThoughtBubble
        intent={{
          target_speed_kmh: 70,
          racing_line_offset_m: 0,
          aggression: 0.5,
          ts: NOW,
        }}
        position={{ x: 123, y: 456 }}
        now={NOW}
      />
    );

    const bubble = screen.getByTestId('agent-thought-bubble');
    // We don't pin a specific transform/left/top form — just assert the
    // values land in the inline style so the parent's coordinate updates
    // actually move the bubble.
    const style = bubble.getAttribute('style') || '';
    expect(style).toContain('123');
    expect(style).toContain('456');
  });
});
