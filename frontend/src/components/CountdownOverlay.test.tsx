import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { CountdownOverlay } from './CountdownOverlay';

describe('CountdownOverlay', () => {
  it('renders countdown number when visible and counting down', () => {
    render(
      <CountdownOverlay
        countdown={3}
        isVisible={true}
        raceStatus="countdown"
      />
    );

    expect(screen.getByText('3')).toBeInTheDocument();
  });

  it('renders GO! when countdown reaches 0 and race starts', () => {
    render(
      <CountdownOverlay
        countdown={0}
        isVisible={false}
        raceStatus="racing"
      />
    );

    expect(screen.getByText('GO!')).toBeInTheDocument();
  });

  it('does not render when not visible and no special state', () => {
    const { container } = render(
      <CountdownOverlay
        countdown={0}
        isVisible={false}
        raceStatus="waiting"
      />
    );

    expect(container.firstChild).toBeNull();
  });

  it('applies correct color classes for countdown numbers', () => {
    const { container } = render(
      <CountdownOverlay
        countdown={2}
        isVisible={true}
        raceStatus="countdown"
      />
    );

    const countdownElement = screen.getByText('2');
    expect(countdownElement).toHaveClass('text-yellow-400');
  });

  it('applies correct color for GO! message', () => {
    render(
      <CountdownOverlay
        countdown={0}
        isVisible={false}
        raceStatus="racing"
      />
    );

    const goElement = screen.getByText('GO!');
    expect(goElement).toHaveClass('text-green-400');
  });
});
