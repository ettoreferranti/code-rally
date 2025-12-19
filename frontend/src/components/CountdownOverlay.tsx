/**
 * Countdown overlay component for race start sequence and finish banner.
 *
 * Displays countdown numbers (3, 2, 1), "GO!" message, and "FINISH!" message
 * with animated transitions.
 */

import { useEffect, useState } from 'react';

interface CountdownOverlayProps {
  countdown?: number;  // Countdown seconds remaining
  isVisible: boolean;  // Whether countdown is active
  raceStatus?: string;  // Race status: 'waiting', 'countdown', 'racing', 'finished'
  isFinished?: boolean;  // Whether race is finished
}

export const CountdownOverlay: React.FC<CountdownOverlayProps> = ({
  countdown,
  isVisible,
  raceStatus,
  isFinished
}) => {
  const [displayText, setDisplayText] = useState<string>('');
  const [isAnimating, setIsAnimating] = useState(false);
  const [showGo, setShowGo] = useState(false);
  const [hasShownGo, setHasShownGo] = useState(false);
  const [showFinish, setShowFinish] = useState(false);
  const [hasShownFinish, setHasShownFinish] = useState(false);

  useEffect(() => {
    // Reset when race status changes to waiting or countdown (new race)
    if (raceStatus === 'waiting' || raceStatus === 'countdown') {
      setHasShownGo(false);
      setHasShownFinish(false);
      setShowGo(false);
      setShowFinish(false);
      setDisplayText('');
      setIsAnimating(false);
    }
  }, [raceStatus]);

  useEffect(() => {
    // Show FINISH banner when race ends
    if (isFinished && !hasShownFinish) {
      setShowFinish(true);
      setHasShownFinish(true);
      setDisplayText('FINISH!');
      setIsAnimating(true);

      // Hide after 2 seconds
      const timer = setTimeout(() => {
        setShowFinish(false);
        setDisplayText('');
        setIsAnimating(false);
      }, 2000);

      return () => clearTimeout(timer);
    }
  }, [isFinished, hasShownFinish]);

  useEffect(() => {
    // Don't show anything if not during countdown
    if (!isVisible || raceStatus !== 'countdown') {
      // Check if countdown just finished (transition from countdown to racing)
      if (raceStatus === 'racing' && countdown !== undefined && countdown <= 0 && !hasShownGo) {
        setShowGo(true);
        setHasShownGo(true);
        setDisplayText('GO!');
        setIsAnimating(true);

        // Hide after 1 second
        const timer = setTimeout(() => {
          setShowGo(false);
          setDisplayText('');
          setIsAnimating(false);
        }, 1000);

        return () => clearTimeout(timer);
      }

      // If not showing GO, clear display
      if (!showGo && !showFinish) {
        setDisplayText('');
        setIsAnimating(false);
      }
      return;
    }

    // Display countdown number (rounded up)
    if (countdown !== undefined && countdown > 0) {
      const countdownNumber = Math.ceil(countdown);
      setDisplayText(countdownNumber.toString());
      setIsAnimating(true);
    }
  }, [countdown, isVisible, raceStatus, hasShownGo, showGo, showFinish]);

  if (!displayText) {
    return null;
  }

  return (
    <div className="absolute inset-0 flex items-center justify-center pointer-events-none z-50">
      <div
        className={`
          text-9xl font-bold text-white
          ${displayText === 'GO!' ? 'text-green-400' : ''}
          ${displayText === 'FINISH!' ? 'text-blue-400' : ''}
          ${!['GO!', 'FINISH!'].includes(displayText) ? 'text-yellow-400' : ''}
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
