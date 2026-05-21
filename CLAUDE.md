# CodeRally - Development Guide for Claude

## Project Overview

CodeRally is a top-down 2D racing game. Drivers can be human (keyboard),
Python (sandboxed RestrictedPython bot), or LLM (local MLX model with a
per-bot system prompt). All three coexist in a lobby.

**Repository**: https://github.com/ettoreferranti/code-rally
**Owner**: Ettore Ferranti (@ettoreferranti)

## App shape

Two top-level areas:

- **Play** (`/lobbies` and `/lobby/:id`) — browse or create a lobby,
  add bots from the user's library, start race. Lobby create form
  exposes three track-shape presets: **difficulty** (corner density),
  **length** (short/medium/long), **curves** (flowing/mixed/twisty).
  These travel on `LobbySettings` and are reused on every regenerate.
  The race screen is `/race?session_id=...&lobby_id=...` and is reached
  only through a lobby (no standalone entry point). The "New Track"
  button on the race screen sends a `regenerate_track` WS message
  that swaps the track in-place for everyone in the session (refused
  while the race is actively RACING — see "Multiplayer track reroll"
  below). The "Share Lobby" button copies `/lobby/<id>` for invites.
- **Tinker** (`/tinker`) — unified bot library. Single list with
  `[PY]`/`[LLM]` badges per row. Add wizard asks the kind first,
  then collects kind-specific fields (Monaco editor for Python;
  model preset dropdown + "Driving strategy" textarea for LLM —
  see "LLM prompt: strategy vs protocol" below).

The old `/practice`, `/multiplayer`, and `/editor` pages were
removed; `/editor` redirects to `/tinker` for legacy URLs.

## Tech Stack

### Backend
- **Framework**: FastAPI (Python 3.11+)
- **Database**: SQLite with SQLAlchemy ORM. Single unified `bots`
  table — `kind` column discriminates 'python' vs 'llm'.
  Idempotent column-add migration in `app/database.py`.
- **WebSocket**: FastAPI WebSocket for real-time game state.
- **Python bot sandbox**: RestrictedPython.
- **LLM bot runtime**: MLX (Apple Silicon only, optional install via
  `requirements-agents.txt`). Two-tier agent: ~1Hz strategist outputs
  structured Intent JSON, 20Hz deterministic Controller converts
  Intent to engine bool flags.
- **Testing**: pytest. ~430 tests.

### Frontend
- **Framework**: React 18 + TypeScript + Vite
- **Rendering**: HTML5 Canvas (2D); thought-bubble overlay as DOM.
- **Code Editor**: Monaco Editor (Python bots only).
- **Testing**: Vitest + React Testing Library.

## Project Structure

```
code-rally/
├── backend/
│   ├── app/
│   │   ├── api/routes/    # FastAPI routes (lobbies, bots, llm-models, game WS)
│   │   ├── core/          # Game engine, physics, track, lobby_manager
│   │   ├── agents/        # LLM strategist + controller + MLX runtime
│   │   │   ├── llm_model_presets.json    # Curated MLX model list (editable)
│   │   │   ├── llm_strategist.py
│   │   │   ├── controller.py
│   │   │   ├── observation.py
│   │   │   ├── llm_bot.py
│   │   │   └── mlx_runtime.py
│   │   ├── models/        # SQLAlchemy: User, unified Bot (kind + llm fields)
│   │   ├── services/      # bot_service, user_service
│   │   ├── bot_runtime/   # RestrictedPython sandbox + bot types
│   │   ├── database.py    # init_db + idempotent column-add migration
│   │   └── config.py
│   ├── tests/
│   ├── requirements.txt
│   ├── requirements-agents.txt  # Optional MLX deps (Apple Silicon)
│   └── main.py
├── frontend/
│   ├── src/
│   │   ├── pages/         # Home (tiles), LobbyBrowser, LobbyWaitingRoom,
│   │   │                   #  MultiplayerRace, Tinker, JoinLobby
│   │   ├── components/    # Layout, UserMenu, UserSwitcher, BotEditor,
│   │   │                   #  AgentThoughtBubble, RaceHUD, ...
│   │   ├── game/          # Canvas renderer, game loop, types,
│   │   │                   #  state interpolation
│   │   └── services/      # botApi (incl. /llm-models), gameWebSocket,
│   │                       #  lobbyApi
│   ├── public/
│   └── package.json
├── docs/
│   ├── architecture.md
│   ├── bot-api.md
│   └── requirements.md
└── CLAUDE.md
```

## Development Workflow

**CRITICAL RULE**: Test-Driven Development is **mandatory**. For every new feature, bug fix, or code change:
1. Write tests FIRST (unit, integration, or regression as appropriate)
2. Implement the feature/fix
3. Verify all tests pass
4. Never commit code without corresponding tests

### Working on GitHub Issues

1. Each task is tracked as a GitHub issue in the repository
2. Issues are organised by milestone (M1-M6) and labelled by component
3. When assigned an issue, always:
   - Read the issue description and acceptance criteria
   - Check related issues and the relevant epic
   - Follow the architecture in `docs/architecture.md`
   - **Write tests BEFORE or DURING implementation** (TDD approach preferred):
     - **Unit tests** for new functions, methods, and classes
     - **Integration tests** for API endpoints and multi-component interactions
     - **Regression tests** for bug fixes to prevent recurrence
     - **End-to-end tests** for complete user workflows when applicable
   - Update documentation if APIs change

### Issue Completion Workflow

**IMPORTANT**: When you complete an issue, follow this workflow:

1. **Run All Tests**: Before asking for approval, run the complete test suite:
   - Backend: `cd backend && ./venv/bin/python -m pytest tests/ -v`
   - Frontend: `cd frontend && npm test`
   - Present test results summary showing all tests passing
   - If tests fail, fix them before proceeding
2. **Ask for Approval**: Present the completed work and ask the user to verify/approve
3. **Update Documentation**: Automatically update any relevant documentation:
   - Update `docs/` files if architecture or APIs changed
   - Update README.md if setup instructions changed
   - Update bot-api.md if bot interface changed
4. **Verify Test Coverage**: Ensure comprehensive test coverage was implemented:
   - ✅ Unit tests exist for all new functions/methods
   - ✅ Integration tests exist for new API endpoints
   - ✅ Regression tests exist for bug fixes
   - ✅ End-to-end tests exist for new user workflows
   - ✅ All existing tests still pass (verified in Step 1)
   - **Note**: Tests should have been written during implementation (see Step 3 in "Working on GitHub Issues")
5. **Commit and Push**: After approval, automatically commit and push:
   - Use conventional commit format: `feat:`, `fix:`, `docs:`, `test:`, `refactor:`
   - Reference issue number: `feat: implement feature (#123)`
   - Include descriptive commit message explaining what was done
   - Add Claude Code attribution footer
6. **Close Issue**: Automatically close the GitHub issue with a comment:
   - Summarize what was implemented
   - List acceptance criteria that were met
   - Include any setup/usage instructions if needed

**Example Commit Message**:
```
feat: implement React frontend project structure (#96)

- Set up React 19 + TypeScript with Vite 7
- Configure Tailwind CSS v3 for styling
- Add React Router with Layout component
- Create project structure (components, game, editor, services)
- Implement placeholder pages (Home, Race, Editor)

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
```

### Fetching Issue Details

Use the GitHub CLI to get issue details:
```bash
gh issue view <number>
```

Or list issues by milestone:
```bash
gh issue list --milestone "M1: Foundation"
```

### Committing Code

- Use conventional commits: `feat:`, `fix:`, `docs:`, `test:`, `refactor:`
- Reference issue numbers: `feat: implement car physics model (#97)`
- Keep commits focused and atomic

### Branch Strategy

- Create feature branches from `main`: `feature/<issue-number>-short-description`
- Example: `feature/97-car-physics-model`

## Coding Standards

### Python (Backend)

```python
# Use type hints
def calculate_velocity(speed: float, heading: float) -> tuple[float, float]:
    ...

# Use dataclasses for data structures
@dataclass
class CarState:
    position: tuple[float, float]
    velocity: tuple[float, float]
    heading: float

# Use async for I/O operations
async def get_user(user_id: int) -> User:
    ...

# Document public functions
def apply_friction(velocity: Vector2, surface: str, dt: float) -> Vector2:
    """Apply surface friction to velocity.
    
    Args:
        velocity: Current velocity vector
        surface: Surface type (asphalt, gravel, ice, wet)
        dt: Delta time in seconds
        
    Returns:
        New velocity after friction applied
    """
    ...
```

### TypeScript/React (Frontend)

```typescript
// Use functional components with hooks
const GameCanvas: React.FC<GameCanvasProps> = ({ gameState, onInput }) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  
  useEffect(() => {
    // Canvas setup
  }, []);
  
  return <canvas ref={canvasRef} />;
};

// Use TypeScript interfaces
interface CarState {
  position: [number, number];
  velocity: [number, number];
  heading: number;
}

// Use named exports
export { GameCanvas, useGameLoop, renderCar };
```

### CSS

- Use CSS modules or Tailwind CSS
- Follow BEM naming if using plain CSS
- Keep styles co-located with components

### Logging and Debugging

**CRITICAL**: Use proper logging libraries, not direct console/print statements.

#### Backend (Python)
```python
import logging

logger = logging.getLogger(__name__)

# Use appropriate log levels
logger.debug('Detailed information for debugging')     # Development only
logger.info('General informational messages')          # Important events
logger.warning('Warning messages')                      # Potential issues
logger.error('Error messages')                          # Errors that don't crash
logger.critical('Critical errors')                      # Severe errors

# ❌ DON'T: Use print() in production code
print("Game state updated")  # WRONG - floods console

# ✅ DO: Use logging with appropriate levels
logger.debug("Game state updated: tick=%d", tick)  # Only shows in DEBUG mode
```

#### Frontend (TypeScript/React)
```typescript
// Use console methods with appropriate levels
console.debug('Detailed debug info');    // Development only
console.log('General information');      // Important events
console.warn('Warning messages');        // Potential issues
console.error('Error messages');         // Actual errors

// ❌ DON'T: Log on every render/tick
useEffect(() => {
  console.log('State updated');  // WRONG - floods console at 60 FPS
}, [gameState]);

// ✅ DO: Log only important state changes
useEffect(() => {
  if (gameState?.raceInfo.raceStatus === 'finished') {
    console.log('Race finished!');  // Only logs once when race ends
  }
}, [gameState?.raceInfo.raceStatus]);
```

#### Cleanup Rules
1. **Remove debug logging** after fixing bugs - don't leave console floods behind
2. **Use DEBUG level** for verbose logging during development
3. **Never log on every tick/frame** - this creates unusable console output
4. **Keep production logs clean** - only log important events (errors, state transitions, user actions)
5. **Use structured logging** with context (e.g., `logger.info('Race started', extra={'race_id': race_id})`)

## Key Architectural Decisions

### Server-Authoritative Game State

All game physics run on the server. Clients send inputs and receive state updates. This prevents cheating but requires good latency handling.

```
Client → Server: { type: "input", actions: { accelerate: true, turn_left: false, ... } }
Server → Client: { type: "game_state", tick: 1234, cars: [...], race: {...} }
```

### Bot Execution

User Python code runs in RestrictedPython sandbox:
- No file/network access
- No dangerous imports
- 10ms execution timeout per tick
- 50MB memory limit

Bot lifecycle:
1. Code validated on save
2. Bot instantiated at race start
3. `on_tick()` called every ~50ms (20Hz)
4. Event callbacks for collisions, checkpoints, finish line
5. State persisted after race

**Note**: Rally stages use point-to-point format (not looping circuits). See `docs/rally-stage-migration.md` for details.

### Physics Model

Simulation-style with drift:
- 60Hz physics tick rate
- Grip coefficient varies by surface
- Drift occurs when grip exceeded
- Elastic collision response
- Off-track speed penalty

Key physics parameters are in `backend/app/config.py`.

### Track shape (config-driven)

`backend/app/config.py` exposes the stage-generator knobs (`STAGE_*`):
start/end coords, num control points per difficulty, serpentine
amplitude and frequency. The user-facing **length** and **curves**
lobby presets multiply/override these — see
`TrackGenerator.LENGTH_FACTORS` and `CURVES_PRESETS` in
`backend/app/core/track.py`. Unknown preset strings fall back to
the config defaults rather than crashing.

### Multiplayer track reroll

The "New Track" button calls `wsRef.regenerateTrack(seed)`. The
backend handler (`backend/app/api/routes/game.py`) refuses while
`RaceStatus.RACING`, otherwise generates a new track using the
lobby's `track_difficulty`/`track_length`/`track_curves`, calls
`GameEngine.reset_to_new_track(new_track)` (resets cars + race
state to WAITING), and broadcasts `track_changed`. Clients swap
the track in `setTrack` so the renderer picks it up immediately;
nobody is disconnected and bots stay in the session.

### Missed-checkpoint detection

`PlayerState.missed_checkpoint_tick` is set when the driver crosses
a checkpoint AHEAD of `current_checkpoint` (i.e. skipped one). The
crossing is NOT credited — the driver still has to go back. The
field rides on the per-player snapshot; the frontend flashes a red
banner for ~3s when it sees a new tick value for the local player.
See `_check_checkpoint_progress` and `_crossed_checkpoint_forward`
in `backend/app/core/engine.py`.

### LLM prompt: strategy vs protocol

The system prompt sent to MLX is assembled in two parts (see
`backend/app/agents/llm_strategist.py`):

- `DEFAULT_STRATEGY_PROMPT` — persona + racing pedagogy
  (braking/apex/exit, surface adjustments, nitro and tactical
  guidance). User-editable via the Tinker "Driving strategy"
  textarea.
- `PROTOCOL_PROMPT` — JSON output format, field ranges (including
  the optional `use_nitro`, `target_opponent_index`, `tactic` fields
  added in the driving uplift), examples, "no prose/markdown/code
  fences". **Invariant**, always appended. Must stay in sync with
  `_parse_intent` and the `Intent` pydantic model. Not exposed to
  users.

`build_prompt(observation, system_prompt)` emits
`<strategy>\n\n<PROTOCOL>\n\nObservation:...`. Existing user-saved
prompts that still contain old JSON-format boilerplate aren't
migrated — they're just redundant, since the protocol is appended
on top regardless.

### LLM Intent + observation (driving uplift)

`Intent` (pydantic, `backend/app/agents/intent.py`) carries six
fields: `target_speed_kmh`, `racing_line_offset_m`, `aggression`
(originals), plus `use_nitro: bool=False`,
`target_opponent_index: 0|1|None=None`, and
`tactic: "race"|"overtake"|"block"|"pit" = "race"`. Defaults
preserve backward compatibility — old 3-field JSON still parses.

The observation (`backend/app/agents/observation.py`) is a 16-line
fixed-shape text block. Beyond the original speed/heading/surface/
edges/3 checkpoints/2 opponents, it now exposes `nitro: N ready
(active: yes|no)`, `race_pos: P<n>/<total>`, `to_finish: <m> m`,
`next_turn: <dir>, sharpness=<f>`, `upcoming_surface: <surface>`,
and a `closing`/`opening` descriptor on each opponent.

`backend/app/core/terrain.py` computes the real geometry behind
those new fields:

- `boundary_distances(position, track)` — true left/right edge
  distances from the nearest segment (replaces the old hardcoded
  `100.0` placeholder).
- `upcoming_turn(track, idx)` — direction (`"left"|"right"|"straight"`)
  and sharpness 0..1 from the angle at the next checkpoint.
- `upcoming_surface(track, idx)` — surface at the segment closest
  to the next checkpoint.

The `Controller` (`backend/app/agents/controller.py`) consumes these:

- **Two-checkpoint blended lookahead** (`_LOOKAHEAD_BLEND_RADIUS_M`
  default 60m). Outside the blend radius the steering target is
  `cp[next]` (legacy behaviour). Inside, it slides toward
  `cp[next+1]`, giving real corner-anticipation geometry.
- `racing_line_offset_m` is applied perpendicular to the **blended**
  track direction (`cp[next] → cp[next+1]`).
- `intent.use_nitro` flows through to `ControlInputs.nitro`, gated
  on `state.car.nitro_charges > 0`.
- `tactic` resolution (see `_resolve_offset`): `overtake` shifts the
  offset to the opposite side of the targeted opponent; `pit` shifts
  toward them; `block` claims the inside of the upcoming turn (no
  target needed); `race` (default) uses `racing_line_offset_m`
  verbatim. When a tactic references a missing opponent, the
  resolver falls through to the LLM's offset rather than crashing.

### LLM cold-start warmup

`engine.start_agents` (called once after `start_race` triggers
COUNTDOWN) now warms each LLM bot up BEFORE spawning the background
strategist task:

1. Build the start-position `BotGameState` for each LLM bot and
   pre-feed it via `LLMBot.warmup_from_state(state)`. Without this
   the strategist's first 1–3 ticks during countdown all see
   `observation=None` and return `None`.
2. Run one synchronous `LLMBot.warmup_tick()` per LLM bot. The
   shared MLX executor serialises these so they run sequentially;
   per-bot timeout is `engine._WARMUP_TIMEOUT_S` (2.5 s default).
3. Spawn the regular background loops.

End result: by green light, each LLM driver has a valid Intent
cached, so the controller starts on the LLM's plan rather than the
30 km/h fallback cruise. This closes the historical 1–2 s gap
between LLM cars and humans/Python bots at race start.

### Thought bubble (visibility)

`engine._player_snapshot` ships all six Intent fields under
`agent_intent` (was three pre-uplift). `AgentThoughtBubble.tsx`
renders:

- speed (km/h) + nitro ⚡ on the top line when `use_nitro=true`,
- aggression word (cautious/steady/aggressive),
- racing-line arrow + magnitude when offset is outside ±0.5 m
  (`offset_label`),
- tactic label with target slot (`#1` / `#2`) when `tactic != "race"`.

`gameWebSocket.ts::agent_intent` and `types.ts::AgentIntent` mirror
the backend shape. The three new fields are typed as optional for
forward compatibility (older recordings or older backends omit them).

## Testing Requirements

### Backend Tests (~430 tests)

```bash
cd backend
./venv/bin/python -m pytest tests/ -v
```

**Test Suites:**
- `test_physics.py` (69 tests): Vector2 math, car physics, drift mechanics
- `test_new_features.py` (19 tests): Regression tests for features #107, #108, #110
  - Split times tracking
  - Position ranking
  - Nitro boost system
- `test_engine.py` (18 tests): End-to-end race scenarios with game engine
  - Checkpoint tracking integration
  - Position ranking integration
  - Nitro boost integration
  - Race lifecycle states
- `test_track.py` (26 tests): Track generation and validation
- `test_health.py` (4 tests): API health endpoints

**Test Types:**
- Unit tests for physics calculations, game logic, and data structures
- Integration tests for game engine and API endpoints
- Regression tests to ensure features don't break
- End-to-end tests simulating complete race scenarios

**Important:** All tests use tick-based simulation (no `time.sleep()`), making them fast and deterministic.

### Frontend Tests (5+ tests)

```bash
cd frontend
npm test
```

**Framework:** Vitest + React Testing Library

**Test Suites:**
- `CountdownOverlay.test.tsx` (5 tests): Race countdown and finish overlays
- Component tests for UI elements
- Integration tests for game state management

**Test Configuration:**
- Setup file: `src/test/setup.ts`
- Config: `vite.config.ts`
- Scripts: `npm test`, `npm run test:watch`, `npm run test:ui`

## Running Locally

Quickest path: `./run_dev.sh` at the repo root starts both servers
with the right flags and prints the LAN URLs so other devices on
the Wi-Fi (phone, iPad, another laptop) can connect.

Manual:

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Note: `--host 0.0.0.0` is required for any device other than the
host machine to reach the API (Vite's frontend auto-detects the
backend on the same hostname:8000 — see
`frontend/src/config.ts::getApiBaseUrl`).

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Access at http://localhost:5173 (or `http://<your-LAN-IP>:5173`
from another device on the same network).

## Milestones Overview

| Milestone | Focus | Key Deliverable |
|-----------|-------|-----------------|
| M1: Foundation | Core engine, physics, rendering | Single car driving on point-to-point stage |
| M2: Racing | Collisions, checkpoints, surfaces | Complete rally stage |
| M3: Bot Framework | Sandbox, API, editor | Programmable bots |
| M4: Multiplayer | WebSocket, sync | Multi-player stages |
| M5: Progression | Users, garage, upgrades | Persistent progress |
| M6: Polish | Championship, debugging | Release-ready |

## Issue Labels

- `epic` - Large feature area
- `user-story` - Implementable task
- `future-development` - Backlog (not current scope)
- `milestone-1` to `milestone-6` - Phase assignment
- `backend` / `frontend` - Component
- `game-engine` / `bot-system` - Subsystem

## Important Files Reference

| File | Purpose |
|------|---------|
| `backend/app/config.py` | All game parameters (incl. `STAGE_*` track-shape knobs) |
| `backend/app/core/physics.py` | Physics simulation |
| `backend/app/core/engine.py` | Main game loop; checkpoint + missed-checkpoint detection; `reset_to_new_track` |
| `backend/app/core/track.py` | Track generation; `LENGTH_FACTORS` / `CURVES_PRESETS` |
| `backend/app/core/lobby.py` | `LobbySettings` (incl. `track_length`, `track_curves`) |
| `backend/app/api/routes/game.py` | Game WS; `regenerate_track` handler; `_serialize_track` |
| `backend/app/agents/llm_strategist.py` | `DEFAULT_STRATEGY_PROMPT` + invariant `PROTOCOL_PROMPT`; `build_prompt` |
| `backend/app/agents/intent.py` | `Intent` schema (incl. `use_nitro`, `target_opponent_index`, `tactic`) |
| `backend/app/agents/observation.py` | 16-line text observation; closure descriptor on opponents |
| `backend/app/agents/controller.py` | 20Hz controller; two-checkpoint blend; `_resolve_offset` for tactic |
| `backend/app/core/terrain.py` | Real boundary / upcoming-turn / upcoming-surface computation |
| `backend/app/bot_runtime/sandbox.py` | Bot execution |
| `frontend/src/game/renderer.ts` | Canvas rendering (stylized cars, drift/nitro effects) |
| `frontend/src/game/input.js` | Keyboard handling |
| `frontend/src/services/gameWebSocket.ts` | WS client; `track_changed`, `regenerateTrack` |
| `frontend/src/pages/MultiplayerRace.tsx` | Race screen; missed-checkpoint banner; Share Lobby / New Track buttons |

## Common Tasks

### Adding a new API endpoint

1. Create route in `backend/app/api/routes/`
2. Add business logic in `backend/app/services/`
3. Update OpenAPI docs with docstrings
4. Add tests in `backend/tests/`
5. Run test suite to verify: `cd backend && ./venv/bin/python -m pytest tests/ -v`

### Adding a new React component

1. Create component in appropriate `frontend/src/` folder
2. Export from index file
3. Add TypeScript interfaces
4. Add component tests (e.g., `ComponentName.test.tsx`)
5. Run test suite to verify: `cd frontend && npm test`

### Modifying game physics

1. Update parameters in `backend/app/config.py`
2. Implement changes in `backend/app/core/physics.py`
3. Update existing tests in `backend/tests/test_physics.py`
4. Add regression tests if fixing a bug
5. Run test suite to verify: `cd backend && ./venv/bin/python -m pytest tests/test_physics.py -v`
6. Update bot API docs if sensor data changes

### Adding a new feature

1. Write unit tests first (TDD approach recommended)
2. Implement the feature
3. Add integration/end-to-end tests if needed
4. Add regression tests to prevent future breakage
5. Run full test suite: Backend + Frontend
6. Update documentation if public APIs changed

## Contact

- **Repository**: https://github.com/ettoreferranti/code-rally
- **Issues**: https://github.com/ettoreferranti/code-rally/issues
