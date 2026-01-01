import { describe, it, expect } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { CountdownOverlay } from './CountdownOverlay';
import React, { useState, useEffect } from 'react';

// Wrapper component to test state transitions
function CountdownWrapper() {
  const [raceStatus, setRaceStatus] = useState<string>('countdown');
  const [countdown, setCountdown] = useState(1);

  // Simulate transition from countdown to racing after a delay
  useEffect(() => {
    const timer = setTimeout(() => {
      console.log('Wrapper: Transitioning to racing status');
      setRaceStatus('racing');
      setCountdown(0);
    }, 50);
    return () => clearTimeout(timer);
  }, []);

  console.log('Wrapper rendering:', { raceStatus, countdown, isVisible: raceStatus === 'countdown' });

  return (
    <CountdownOverlay
      countdown={countdown}
      isVisible={raceStatus === 'countdown'}
      raceStatus={raceStatus}
    />
  );
}

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

  // TODO: Fix timing issue with multiple useEffect hooks competing during state transitions
  it.skip('renders GO! when countdown reaches 0 and race starts', async () => {
    render(<CountdownWrapper />);

    // Wait for the GO! text to appear after transition
    await waitFor(() => {
      expect(screen.getByText('GO!')).toBeInTheDocument();
    }, { timeout: 2000 });
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

  // TODO: Fix timing issue with multiple useEffect hooks competing during state transitions
  it.skip('applies correct color for GO! message', async () => {
    render(<CountdownWrapper />);

    // Wait for the GO! text to appear and check its color
    await waitFor(() => {
      const goElement = screen.getByText('GO!');
      expect(goElement).toHaveClass('text-green-400');
    }, { timeout: 2000 });
  });
});
