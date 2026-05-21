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
 *
 * The bubble now surfaces all six Intent fields the LLM can emit:
 *   - target_speed_kmh   → bold number, top line
 *   - aggression         → word (cautious / steady / aggressive)
 *   - racing_line_offset → arrow + metres when non-zero
 *   - use_nitro          → ⚡ marker when true
 *   - tactic + target    → small line when tactic ≠ "race"
 */

import type { AgentIntent, AgentTactic } from '../game/types';

interface AgentThoughtBubbleProps {
  intent?: AgentIntent;
  position: { x: number; y: number };
  // Injectable "now" (Unix seconds). Defaults to Date.now()/1000. Tests
  // pin this to make staleness deterministic.
  now?: number;
}

const STALE_AFTER_S = 2;
// Offsets within ±0.5 m read as "centre" — don't clutter the bubble with
// micro-offsets that don't change the racing line meaningfully.
const OFFSET_DEADBAND_M = 0.5;

function aggressionHint(aggression: number): string {
  if (aggression < 0.33) return 'cautious';
  if (aggression < 0.66) return 'steady';
  return 'aggressive';
}

function offsetLabel(offset: number): string | null {
  if (Math.abs(offset) < OFFSET_DEADBAND_M) return null;
  const arrow = offset > 0 ? '→' : '←';
  return `${arrow} ${Math.abs(offset).toFixed(1)} m`;
}

function tacticLabel(
  tactic: AgentTactic,
  targetIndex: number | null | undefined,
): string | null {
  if (tactic === 'race') return null;
  if (tactic === 'block') return 'block';
  // overtake / pit reference an opponent slot from the observation. Slot
  // 0 / 1 in the protocol map to the nearest / second-nearest opponent
  // the LLM was shown. Display them 1-indexed to match the observation
  // "opponent[1]" / "opponent[2]" labels.
  const targetSuffix =
    targetIndex === 0 || targetIndex === 1 ? ` #${targetIndex + 1}` : '';
  return `${tactic}${targetSuffix}`;
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

  const offset = offsetLabel(intent.racing_line_offset_m);
  const tactic = tacticLabel(
    intent.tactic ?? 'race',
    intent.target_opponent_index ?? null,
  );
  const nitro = intent.use_nitro === true;

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
      <div className="font-semibold flex items-center gap-1">
        <span>{Math.round(intent.target_speed_kmh)} km/h</span>
        {nitro && (
          <span data-testid="agent-thought-nitro" className="text-cyan-300">
            ⚡
          </span>
        )}
      </div>
      <div className="text-yellow-300">{aggressionHint(intent.aggression)}</div>
      {offset && (
        <div data-testid="agent-thought-offset" className="text-gray-300">
          {offset}
        </div>
      )}
      {tactic && (
        <div data-testid="agent-thought-tactic" className="text-red-300">
          {tactic}
        </div>
      )}
    </div>
  );
};

export default AgentThoughtBubble;
