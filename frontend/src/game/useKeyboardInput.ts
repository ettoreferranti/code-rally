/**
 * Custom hook for handling keyboard input in the game.
 */

import { useEffect, useState, useCallback } from 'react';
import type { InputState } from './types';

/**
 * Key mappings for game controls.
 * Supports both WASD and arrow keys.
 */
const KEY_MAPPINGS = {
  accelerate: ['KeyW', 'ArrowUp'],
  brake: ['KeyS', 'ArrowDown'],
  turnLeft: ['KeyA', 'ArrowLeft'],
  turnRight: ['KeyD', 'ArrowRight'],
  nitro: ['Space']
};

/**
 * Keys that should have their default browser behavior prevented.
 */
const PREVENT_DEFAULT_KEYS = [
  'Space',
  'ArrowUp',
  'ArrowDown',
  'ArrowLeft',
  'ArrowRight'
];

/**
 * Hook to track keyboard input state for game controls.
 *
 * @returns Current input state with all actions (true = pressed, false = not pressed)
 */
export function useKeyboardInput(): InputState {
  const [inputState, setInputState] = useState<InputState>({
    accelerate: false,
    brake: false,
    turnLeft: false,
    turnRight: false,
    nitro: false
  });

  // Track which keys are currently pressed
  const [pressedKeys, setPressedKeys] = useState<Set<string>>(new Set());

  // Update input state based on pressed keys
  const updateInputState = useCallback((keys: Set<string>) => {
    setInputState({
      accelerate: KEY_MAPPINGS.accelerate.some(key => keys.has(key)),
      brake: KEY_MAPPINGS.brake.some(key => keys.has(key)),
      turnLeft: KEY_MAPPINGS.turnLeft.some(key => keys.has(key)),
      turnRight: KEY_MAPPINGS.turnRight.some(key => keys.has(key)),
      nitro: KEY_MAPPINGS.nitro.some(key => keys.has(key))
    });
  }, []);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      // Prevent default browser behavior for game keys
      if (PREVENT_DEFAULT_KEYS.includes(event.code)) {
        event.preventDefault();
      }

      // Add key to pressed keys set
      setPressedKeys(prev => {
        const next = new Set(prev);
        next.add(event.code);
        updateInputState(next);
        return next;
      });
    };

    const handleKeyUp = (event: KeyboardEvent) => {
      // Remove key from pressed keys set
      setPressedKeys(prev => {
        const next = new Set(prev);
        next.delete(event.code);
        updateInputState(next);
        return next;
      });
    };

    // Clear all keys when window loses focus
    const handleBlur = () => {
      setPressedKeys(new Set());
      updateInputState(new Set());
    };

    // Add event listeners
    window.addEventListener('keydown', handleKeyDown);
    window.addEventListener('keyup', handleKeyUp);
    window.addEventListener('blur', handleBlur);

    // Cleanup
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      window.removeEventListener('keyup', handleKeyUp);
      window.removeEventListener('blur', handleBlur);
    };
  }, [updateInputState]);

  return inputState;
}
