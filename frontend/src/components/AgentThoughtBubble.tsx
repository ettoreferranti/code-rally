/**
 * AgentThoughtBubble (issue #156).
 *
 * Surfaces an LLM-driven car's latest strategist intent above the car.
 *
 * Render path: DOM overlay positioned via the camera's worldToScreen()
 * helper (computed by the parent and passed as `position`). Chosen over
 * canvas fillText because:
 *   - CSS handles the fade-on-stale state cleanly via opacity classes,
 *   - the component is unit-testable with React Testing Library,
 *   - styling can evolve without touching the canvas render loop.
 *
 * The component fades to half-opacity when the intent timestamp is more
 * than 2 seconds old. With no intent the component renders nothing.
 */

import type { AgentIntent } from '../game/types';

interface AgentThoughtBubbleProps {
  intent?: AgentIntent;
  position: { x: number; y: number };
  // Injectable "now" (Unix seconds). Defaults to Date.now()/1000. Tests
  // pin this to make staleness deterministic.
  now?: number;
}

const STALE_AFTER_S = 2;

function aggressionHint(aggression: number): string {
  if (aggression < 0.33) return 'cautious';
  if (aggression < 0.66) return 'steady';
  return 'aggressive';
}

export const AgentThoughtBubble: React.FC<AgentThoughtBubbleProps> = ({
  intent,
  position,
  now,
}) => {
  if (!intent) {
    return null;
  }

  const currentTime = now ?? Date.now() / 1000;
  const isStale = currentTime - intent.ts > STALE_AFTER_S;

  return (
    <div
      data-testid="agent-thought-bubble"
      className={
        `absolute pointer-events-none px-2 py-1 rounded-md ` +
        `bg-black bg-opacity-70 text-white text-xs leading-tight ` +
        `border border-yellow-400 shadow-lg ` +
        `transition-opacity duration-300 ` +
        (isStale ? 'opacity-50' : 'opacity-100')
      }
      style={{
        left: `${position.x}px`,
        top: `${position.y}px`,
        transform: 'translate(-50%, calc(-100% - 28px))',
      }}
    >
      <div className="font-semibold">{Math.round(intent.target_speed_kmh)} km/h</div>
      <div className="text-yellow-300">{aggressionHint(intent.aggression)}</div>
    </div>
  );
};

export default AgentThoughtBubble;
