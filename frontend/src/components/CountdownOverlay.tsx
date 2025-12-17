/**
 * Countdown overlay component for race start sequence.
 *
 * Displays countdown numbers (3, 2, 1) and "GO!" message
 * with animated transitions.
 */

import { useEffect, useState } from 'react';

interface CountdownOverlayProps {
  countdown: number;  // Countdown seconds remaining
  isVisible: boolean;  // Whether countdown is active
}

export const CountdownOverlay: React.FC<CountdownOverlayProps> = ({ countdown, isVisible }) => {
  const [displayText, setDisplayText] = useState<string>('');
  const [isAnimating, setIsAnimating] = useState(false);

  useEffect(() => {
    if (!isVisible || countdown <= 0) {
      // Show "GO!" when countdown reaches 0
      if (countdown <= 0 && countdown > -0.5) {
        setDisplayText('GO!');
        setIsAnimating(true);

        // Hide after a short delay
        const timer = setTimeout(() => {
          setIsAnimating(false);
        }, 1000);

        return () => clearTimeout(timer);
      } else {
        setDisplayText('');
        setIsAnimating(false);
      }
      return;
    }

    // Display countdown number (rounded up)
    const countdownNumber = Math.ceil(countdown);
    setDisplayText(countdownNumber.toString());
    setIsAnimating(true);
  }, [countdown, isVisible]);

  if (!displayText) {
    return null;
  }

  return (
    <div className="absolute inset-0 flex items-center justify-center pointer-events-none z-50">
      <div
        className={`
          text-9xl font-bold text-white
          ${displayText === 'GO!' ? 'text-green-400' : 'text-yellow-400'}
          ${isAnimating ? 'animate-pulse' : ''}
          transition-all duration-200
          drop-shadow-[0_0_30px_rgba(255,255,255,0.8)]
        `}
        style={{
          textShadow: '0 0 20px currentColor, 0 0 40px currentColor',
          transform: isAnimating ? 'scale(1)' : 'scale(0.8)',
        }}
      >
        {displayText}
      </div>
    </div>
  );
};
