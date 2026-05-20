# CodeRally Architecture

This document describes the system as it currently ships. For
research-playground next-steps see the open issues; for the
day-to-day developer guide see `CLAUDE.md`.

## System Overview

CodeRally is a client-server web application. The server is the
authoritative source of game state; clients send inputs and render
broadcast snapshots.

```
┌─────────────────┐     WebSocket      ┌────────────────────────────────────┐
│   Browser       │◄──────────────────►│        Backend (FastAPI)            │
│  (Human / spec) │                    │                                     │
└─────────────────┘                    │  ┌─────────┐  ┌─────────────────┐  │
                                       │  │  Game   │  │   Bot Runtimes  │  │
                                       │  │ Engine  │  │ ┌─────────────┐ │  │
                                       │  │ (60Hz)  │  │ │ Python (RP) │ │  │
                                       │  └─────────┘  │ ├─────────────┤ │  │
                                       │       │       │ │ LLM (MLX)   │ │  │
                                       │       │       │ └─────────────┘ │  │
                                       │       │       └─────────────────┘  │
                                       │       ▼                            │
                                       │  ┌──────────────────────────────┐  │
                                       │  │  SQLite (users + bots)       │  │
                                       │  └──────────────────────────────┘  │
                                       └────────────────────────────────────┘
```

There are three driver kinds, all interchangeable in a lobby:
- **Human**: keyboard input over a WebSocket.
- **Python bot**: `BaseBot` subclass running in a RestrictedPython sandbox.
- **LLM bot**: local MLX language model driving via a two-tier
  strategist + controller architecture (#151).

## Design Principles

1. **Server-authoritative state.** All physics, scoring, and surface
   logic runs on the server; clients only render and feed inputs.
2. **Pre-race composition.** All participants (humans, bots) join the
   lobby before the race starts. There is no mid-race bot submission.
3. **Driver-kind uniformity.** A `Bot` row in the DB has a `kind`
   discriminator; the lobby / engine treat both kinds the same end-to-end.
4. **Strict serial MLX inference.** All MLX work funnels through one
   shared worker thread (#163, #167, #170) because Metal command-buffer
   state isn't safe across threads.

## App Shape

Two top-level user areas:

- **Play** (`/lobbies` and `/lobby/:id`) — browse or create a lobby,
  add bots from the user's library, start race. The race screen is
  `/race?session_id=…` and is only reached through a lobby.
- **Tinker** (`/tinker`) — unified bot library. Single list with
  `[PY]` / `[LLM]` badges per row. The Add wizard asks for the kind
  first, then collects kind-specific fields.

The old `/practice`, `/multiplayer`, and `/editor` routes were
removed during the Tinker cleanup; `/editor` redirects to `/tinker`.

## Backend Architecture

### Technology Stack

- **Framework**: FastAPI with WebSocket support.
- **Database**: SQLite via SQLAlchemy. One file at
  `backend/data/coderally.db`. No Alembic; an idempotent
  column-add migration in `app/database.py` upgrades existing dev DBs.
- **Python sandbox**: RestrictedPython (with `_inplacevar_` and other
  guards provided in `app/bot_runtime/sandbox.py`).
- **LLM runtime**: MLX (`mlx-lm`), optional install via
  `backend/requirements-agents.txt`. Apple Silicon only.

### Module Structure

```
backend/
├── app/
│   ├── api/routes/
│   │   ├── health.py
│   │   ├── config.py
│   │   ├── tracks.py
│   │   ├── users.py
│   │   ├── bots.py           # Unified Python + LLM bot CRUD
│   │   ├── lobbies.py        # Lobby REST (create/list/disband)
│   │   ├── game.py           # WebSocket game + lobby handlers
│   │   └── llm_models.py     # GET /llm-models presets endpoint
│   │
│   ├── core/
│   │   ├── engine.py         # Main 60Hz game loop, race lifecycle
│   │   ├── physics.py        # Car physics + drift mechanics
│   │   ├── track.py          # Procedural track generation
│   │   ├── bot_manager.py    # Python-bot dispatch into the engine
│   │   ├── raycast.py        # Bot vision sensors
│   │   ├── lobby.py          # Lobby + LobbyMember dataclasses
│   │   └── lobby_manager.py  # Lobby state + unified add_bot_to_lobby
│   │
│   ├── agents/               # LLM driver (research playground)
│   │   ├── llm_strategist.py # ~1Hz async, observation → Intent
│   │   ├── controller.py     # 20Hz deterministic, Intent → flags
│   │   ├── observation.py    # BotGameState → compact text
│   │   ├── llm_bot.py        # Per-car wrapper for engine dispatch
│   │   ├── mlx_runtime.py    # Per-model_path cache + shared executor
│   │   ├── intent.py         # Pydantic Intent schema
│   │   ├── model_presets.py  # Reads llm_model_presets.json
│   │   └── llm_model_presets.json   # Curated model list (editable)
│   │
│   ├── models/               # SQLAlchemy ORM
│   │   ├── user.py
│   │   └── bot.py            # Unified Bot: kind in {'python', 'llm'}
│   │
│   ├── services/             # Business logic
│   │   ├── user_service.py
│   │   └── bot_service.py    # create_bot, create_llm_bot, update_bot, …
│   │
│   ├── bot_runtime/          # RestrictedPython sandbox
│   │   ├── sandbox.py        # Globals, guards, _inplacevar_
│   │   ├── base_bot.py       # BaseBot class & helpers
│   │   ├── types.py          # BotGameState, BotActions, …
│   │   └── templates/        # Starter bots loaded from Tinker
│   │
│   ├── database.py           # init_db + idempotent column migration
│   └── config.py             # All tunable game parameters
│
├── tests/                    # ~415 tests, all green
└── main.py                   # FastAPI app
```

### Game Engine

Runs at a fixed 60Hz physics tick. Each tick:

1. Update race status (countdown / racing / finished).
2. If racing: every 3rd tick (~20Hz bot tick), call
   `_update_bot_inputs` which dispatches per driver kind:
   - Python bot → `BotManager.get_bot_actions` (RestrictedPython call).
   - LLM bot → `LLMBot.get_inputs` (pulls latest Intent from the
     strategist, runs the deterministic controller).
3. Apply physics step per player (acceleration, braking, turning,
   grip, drag, position update).
4. Handle obstacle / boundary / car-car collisions.
5. Detect checkpoint progress and finish line crossings.
6. Update race positions.

When `RaceStatus.FINISHED` is reached, the engine cancels all
strategist tasks via `_stop_agents()` so they don't keep burning MLX
cycles while the results screen is up (#165).

### Physics Model

Car state: `position`, `velocity`, `heading`, `angular_velocity`,
`is_drifting`, `drift_angle`, `nitro_charges`, `nitro_active`.

Drift is modelled via a grip coefficient per surface (asphalt > wet
> gravel > ice). Lateral velocity is killed by `apply_grip` when
not drifting; off-track applies a grip multiplier penalty.

Coordinate system is **y-DOWN** (canvas convention) — increasing
heading rotates the car clockwise visually (#164). "Right of a
+x-facing driver" is +y in engine coords.

Engine speed → displayed km/h uses the constant `_UNITS_TO_KMH = 0.6`
in `agents/controller.py` and `agents/observation.py`, matching the
frontend `RaceHUD` (#166). MAX_SPEED of 300 engine units/s maps to
~180 km/h (rally-car top speed).

### LLM Agent (two-tier)

```
┌─ Strategist (~1Hz async) ────────┐     ┌─ Controller (20Hz sync) ───┐
│  MLX model output                │     │  Pure-pursuit + speed PD   │
│  observation (text) → JSON       │ →   │  reads latest Intent,      │
│  Intent {target_speed_kmh,       │     │  emits PlayerInput flags   │
│   racing_line_offset_m,          │     │  (accel/brake/turn_*)      │
│   aggression}                    │     │  holds last intent if      │
└──────────────────────────────────┘     │  strategist is late        │
                                          └─────────────────────────────┘
```

- The full prompt sent to the model is assembled in two parts —
  `<user strategy>\n\n<PROTOCOL>\n\nObservation:…` (see `build_prompt`
  in `llm_strategist.py`):
  - `DEFAULT_STRATEGY_PROMPT` — persona + driving heuristics. The
    per-bot override lives on `Bot.system_prompt` and is surfaced as
    the **"Driving strategy"** textarea in Tinker.
  - `PROTOCOL_PROMPT` — JSON output shape, field ranges, examples,
    "no prose/markdown/code fences". **Invariant**, always appended.
    Must stay in sync with `_parse_intent` and the `Intent` pydantic
    model. Not exposed to users — splitting it out keeps users from
    accidentally breaking the I/O contract.
- Call timeout is 2 s; failed calls preserve the previous good Intent.
- The parser tolerates noisy model output: takes the first
  `{ … }` block, then validates against the Intent schema, then
  rejects below the racing floor (`_MIN_TARGET_SPEED_KMH = 30`)
  so "stop"-like outputs don't park the car (#162).
- The controller's speed loop uses **anticipated** error (projects
  ahead by `speed_horizon_ticks = 1.5`) so it brakes before
  overshooting target — eliminates the prior ±40 km/h bang-bang
  oscillation.

### MLX Runtime

`MLXRuntime` instances are cached per `model_path` so two LLM bots
on the same model share weights. But **all generation across all
runtimes is serialised through a single module-level shared
`ThreadPoolExecutor(max_workers=1)`** (#170) — MLX's process-wide
default Metal stream isn't safe for concurrent access even across
different loaded models. Practical ceiling: N=3 LLM bots before the
queue can't keep up with the 1Hz strategist cadence.

### Lobby Model

Two distinct identities on a `Lobby`:

- `creator_player_id` — original creator, stable identity that never
  changes. The Play UI uses it to badge "YOUR LOBBY" rows and to
  permit deletion from the listing.
- `host_player_id` — current host, can start the race. Transfers
  between **human** members on leave. Bots can't host (transferring
  to a bot leaves the lobby unhosted). On a human's join, host
  reclaims to the joiner if the recorded host is absent or non-human.

`LobbySettings` carries three track-shape knobs that are chosen at
lobby-create time, shown read-only in the waiting room, and reused
for every track generated by this lobby (including reroll):

- `track_difficulty` — `easy` / `medium` / `hard` / `extreme`. Drives
  corner density (number of control points).
- `track_length` — `short` / `medium` / `long`. Multiplies the Y-span
  of the stage and `num_points` (`LENGTH_FACTORS` in `track.py`).
- `track_curves` — `flowing` / `mixed` / `twisty`. Overrides
  serpentine frequency + amplitude (`CURVES_PRESETS` in `track.py`).
  `mixed` defers to the config-level `STAGE_SERPENTINE_*` defaults.

Lobbies do NOT auto-disband when empty — empty lobbies live until
the creator (or current host) explicitly disbands via
`DELETE /lobbies/{lobby_id}` (#169).

### In-session track reroll

The race screen's "New Track" button sends a `regenerate_track` WS
message. The handler in `app/api/routes/game.py`:

1. Refuses if `RaceStatus.RACING` (the race is actively in progress).
   `WAITING`, `COUNTDOWN`, `FINISHED` are all permitted.
2. Looks up the lobby (if any) and pulls `track_difficulty` /
   `track_length` / `track_curves` from `LobbySettings`. Direct-mode
   sessions fall back to defaults.
3. Calls `TrackGenerator.generate(...)` with a fresh seed, then
   `GameEngine.reset_to_new_track(new_track)` — swaps the track on
   the engine, resets every player's car to the new start line,
   clears race progress, and puts race state back to `WAITING`.
4. Broadcasts `track_changed` (containing the serialized track) to
   every connected member of the session/lobby. Clients swap the
   track in their renderer state without any disconnect.

### Missed-checkpoint detection

`PlayerState.missed_checkpoint_tick: Optional[int]` is set when a
driver crosses a checkpoint AHEAD of `current_checkpoint` — i.e.
they skipped one (typically by cutting a corner off-track). The
later crossing is NOT credited, so the driver still has to go back
and clear the missed checkpoint to progress. The field rides on the
per-player game_state snapshot; the frontend watches for a new tick
value for the local player and flashes a red "MISSED CHECKPOINT"
banner for ~3 seconds. Implementation lives in
`engine._check_checkpoint_progress` / `_crossed_checkpoint_forward`.

### Database Schema

The actual table set is much smaller than originally envisioned —
cars, garage, race results, etc. are not implemented. The model is:

```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL
);

CREATE TABLE bots (
    id INTEGER PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    kind VARCHAR(20) NOT NULL DEFAULT 'python', -- 'python' | 'llm'
    -- python bots: source code (validated with RestrictedPython).
    -- llm bots: empty string (column is NOT NULL).
    code TEXT NOT NULL DEFAULT '',
    -- llm-only fields:
    model_path VARCHAR(255),
    system_prompt TEXT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL
);
```

Lobbies live in-memory only — they don't persist across server
restarts. Race results are not currently persisted to disk either.

## Frontend Architecture

### Technology Stack

- **React 18** with TypeScript (strict mode).
- **Vite** for dev + build (`npm run build` runs `tsc -b && vite build`).
- **Canvas** for game rendering; **Monaco Editor** for Python bot code.
- **Vitest + React Testing Library** for tests (~34, with 2 pre-existing skips).

### Component Structure

```
frontend/src/
├── pages/
│   ├── Home.tsx                  # Two-tile landing (Play / Tinker)
│   ├── LobbyBrowser.tsx          # /lobbies — create, join, spectate, delete
│   ├── LobbyWaitingRoom.tsx      # /lobby/:id — roster + add-bot picker
│   ├── MultiplayerRace.tsx       # /race — actual race screen
│   ├── Tinker.tsx                # /tinker — unified bot library
│   └── JoinLobby.tsx             # /join/:code — join by code
│
├── components/
│   ├── Layout.tsx                # Header (Play / Tinker / UserMenu)
│   ├── UserMenu.tsx              # Header sign-in / switch / sign-out
│   ├── UserSwitcherModal.tsx     # User selection modal
│   ├── UserSwitcherProvider.tsx  # App-level provider for the modal
│   ├── BotEditor.tsx             # Monaco Python editor + completions
│   ├── AgentThoughtBubble.tsx    # DOM overlay above LLM cars
│   ├── RaceHUD.tsx               # Speed / position / time HUD
│   ├── CountdownOverlay.tsx      # 3-2-1-GO + FINISH banner
│   └── RaceResultsScreen.tsx     # Post-race standings
│
├── game/
│   ├── GameCanvas.tsx            # Canvas render loop
│   ├── renderer.ts               # Drawing primitives + Camera
│   ├── physics.ts                # Local physics (legacy; unused for online)
│   ├── types.ts                  # GameState, CarState, AgentIntent, …
│   ├── StateInterpolation.ts     # 60Hz interpolation between 20Hz states
│   ├── trackUtils.ts
│   ├── checkpointUtils.ts
│   ├── useGameLoop.ts            # Legacy local loop (unused for online)
│   └── useKeyboardInput.ts
│
├── services/
│   ├── lobbyApi.ts               # REST: create / list / disband
│   ├── botApi.ts                 # REST: bot CRUD + LLM presets
│   └── gameWebSocket.ts          # WS client for /game/ws
│
└── App.tsx                       # Router + UserSwitcherProvider
```

### Rendering Pipeline

1. Server broadcasts game state at ~60Hz over WebSocket.
2. `StateBuffer` keeps the last few states; `getInterpolatedState`
   smooths between them for visually continuous motion.
3. `GameCanvas` runs `requestAnimationFrame`, applies camera
   transform, renders track / cars / FX, then computes screen
   coordinates for any LLM-bot thought bubbles and overlays them as
   DOM elements (`AgentThoughtBubble`) on top of the canvas.

## Communication Protocol

### REST endpoints (selected)

```
GET  /lobbies?status=waiting|racing       # List lobbies
POST /lobbies                              # Create lobby
DELETE /lobbies/{id}?player_id=…           # Disband (creator OR host)

GET  /bots/users/{username}/bots           # List a user's bot library
GET  /bots/{id}                            # Get a single bot (incl. code)
POST /bots/users/{username}/bots           # Create bot (python or llm)
PUT  /bots/{id}                            # Update bot

GET  /llm-models                           # Curated MLX preset list
GET  /bots/templates                       # Starter Python bot templates

GET  /users                                # List all users
POST /users/register                       # Idempotent registration
```

### WebSocket: `/game/ws`

Query params: `lobby_id` (lobby mode) **or** `session_id` (race mode)
plus optional `player_id` and `spectate=true`.

**Client → Server**:
```json
{"type": "start_race"}
{"type": "add_bot_to_lobby", "data": {"bot_id": 42}}
{"type": "leave_lobby"}
{"type": "input", "data": {"accelerate": true, "brake": false, "turn_left": false, "turn_right": false, "nitro": false}}
{"type": "regenerate_track", "data": {"seed": 12345}}
{"type": "pong"}
```

**Server → Client**:
```json
{"type": "lobby_joined", "data": {"player_id": "…", "lobby": {…}}}
{"type": "lobby_state", "data": {…}}
{"type": "race_starting", "data": {"game_session_id": "…", "track": {…}}}
{"type": "connected", "data": {"session_id": "…", "player_id": "…", "track": {…}}}
{"type": "game_state", "data": {…full snapshot including per-LLM-car agent_intent and per-player missed_checkpoint_tick…}}
{"type": "track_changed", "data": {"track": {…}}}
{"type": "error", "data": {"message": "…"}}
{"type": "ping"}
```

The `game_state` payload includes `players[id].agent_intent` (target
speed, racing-line offset, aggression, timestamp) only for
LLM-driven cars; the frontend uses it to render thought bubbles.
`players[id].missed_checkpoint_tick` is the server tick at which the
driver last skipped a checkpoint (null if it never happened) — the
frontend uses it to flash a banner. `track_changed` is broadcast
after a successful `regenerate_track` reroll.

## Configuration

`backend/app/config.py` holds all tunable parameters (physics
constants, tick rates, bot limits, race settings). Notable knobs:

```python
TICK_RATE = 60                  # Physics ticks per second
BOT_TICK_RATE = 20              # Bot calls per second
COUNTDOWN_SECONDS = 3
MAX_SPEED = 300.0               # engine units / second
ACCELERATION = 250.0
TURN_RATE = 4.5                 # radians / second
GRIP_ASPHALT = 1.0
GRIP_WET = 0.7
GRIP_GRAVEL = 0.5
GRIP_ICE = 0.25
OFF_TRACK_GRIP_MULTIPLIER = 0.3

# Stage shape (the defaults; lobby presets multiply/override these
# at generate-time — see TrackGenerator.LENGTH_FACTORS / CURVES_PRESETS).
STAGE_START_X / STAGE_START_Y    # high-Y start (bottom of screen)
STAGE_END_X   / STAGE_END_Y      # low-Y end (top of screen → cars drive "up")
STAGE_NUM_POINTS_{EASY|MEDIUM|HARD}
STAGE_SERPENTINE_AMPLITUDE       # peak side-to-side swing (units)
STAGE_SERPENTINE_FREQUENCY       # oscillation half-cycles across the stage
```

The physics constants are exposed via `GET /config/physics` so the
frontend can sync.

Environment variables:
- `LOG_LEVEL` (default `INFO`)
- `MLX_MODEL_PATH` (default `mlx-community/Qwen2.5-1.5B-Instruct-4bit`)

## Security Considerations

1. **Python bot sandboxing** — RestrictedPython blocks file/network
   access, dangerous imports, infinite loops (10ms per-tick timeout).
2. **Trusted LLM agent code** — the strategist + controller live
   under `backend/app/agents/` and are NOT sandboxed. Only the bot's
   `system_prompt` is user-controlled. Don't add `eval`-able
   constructs there.
3. **Input validation** — client `PlayerInput` fields are bool
   flags; the WS handler ignores any extras.
4. **No authentication / authorization** — this is a local dev /
   research project. Users are identified by their typed username,
   no password, no session tokens.

## Testing

- **Backend** (`pytest`): ~415 tests. Run from `backend/`:
  ```bash
  ./venv/bin/python -m pytest tests/ -v
  ```
- **Frontend** (`vitest`): ~34 tests. Run from `frontend/`:
  ```bash
  npm test
  ```
- **MLX-gated**: one integration test under `backend/tests/test_mlx_runtime.py`
  is `skipif`'d when `mlx_lm` isn't installed.

## Future Considerations

- **LoRA fine-tuning** for the LLM bot (deferred phase of #151).
- **Self-play / RL data collection** (deferred).
- **Lobby persistence** across restarts (currently in-memory only).
- **Persistent race results** + leaderboard (only `users` and `bots` persist today).
- **Cloud deployment** would require migrating SQLite → Postgres,
  containerising MLX (or making LLM bots cloud-optional).
