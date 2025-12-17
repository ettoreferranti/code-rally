# CodeRally Architecture

> **Implementation Status**: This document describes the complete target architecture.
> Components marked with ✅ are implemented, 🔄 are partially implemented, and 📋 are planned.
> See "Implementation Status" sections throughout for current state.

## System Overview

CodeRally is a client-server web application with real-time multiplayer capabilities.

```
┌─────────────────┐     WebSocket      ┌─────────────────────────────────┐
│   Browser 1     │◄──────────────────►│                                 │
│   (Human)       │                    │         Backend Server          │
├─────────────────┤     WebSocket      │                                 │
│   Browser 2     │◄──────────────────►│  ┌───────────┐ ┌─────────────┐  │
│   (Human)       │                    │  │   Game    │ │     Bot     │  │
├─────────────────┤     WebSocket      │  │  Engine   │ │   Runtime   │  │
│   Browser 3     │◄──────────────────►│  │           │ │  (Sandbox)  │  │
│   (Spectator)   │                    │  └───────────┘ └─────────────┘  │
└─────────────────┘                    │        │              │         │
                                       │        ▼              ▼         │
                                       │  ┌─────────────────────────┐   │
                                       │  │     SQLite Database     │   │
                                       │  └─────────────────────────┘   │
                                       └─────────────────────────────────┘
```

## Design Principles

1. **Server-Authoritative**: All game state computed server-side to prevent cheating
2. **Sandboxed Bot Execution**: User Python code runs in restricted environment
3. **Real-time Sync**: WebSocket for low-latency game state updates
4. **Modular Design**: Clear separation between game engine, bot runtime, and API

## Backend Architecture

### Technology Stack

- **Framework**: FastAPI (async, WebSocket support)
- **Database**: SQLite (simple, file-based, easy migration path)
- **Bot Sandbox**: RestrictedPython
- **Task Queue**: asyncio (built-in async handling)

### Module Structure

```
backend/
├── app/
│   ├── api/              # REST and WebSocket endpoints ✅
│   │   ├── routes/       # Route definitions ✅
│   │   │   ├── health.py    # Health checks ✅
│   │   │   ├── config.py    # Configuration API ✅
│   │   │   ├── tracks.py    # Track generation ✅
│   │   │   └── game.py      # WebSocket game API ✅
│   │
│   ├── core/             # Game engine ✅
│   │   ├── engine.py     # Main game loop ✅
│   │   ├── physics.py    # Physics simulation ✅
│   │   └── track.py      # Track generation ✅
│   │
│   ├── models/           # Database models 📋 (Planned for M5)
│   │   ├── user.py       # 📋 Not yet implemented
│   │   ├── car.py        # 📋 Not yet implemented
│   │   ├── bot.py        # 📋 Not yet implemented
│   │   └── race.py       # 📋 Not yet implemented
│   │
│   ├── services/         # Business logic 📋 (Planned for M4-M5)
│   │   ├── auth.py       # 📋 Authentication
│   │   ├── garage.py     # 📋 Car management
│   │   ├── race.py       # 📋 Race management
│   │   └── leaderboard.py # 📋 Leaderboard
│   │
│   ├── bot_runtime/      # Sandboxed execution 📋 (Planned for M3)
│   │   ├── sandbox.py    # 📋 RestrictedPython setup
│   │   ├── api.py        # 📋 Bot API interface
│   │   └── validator.py  # 📋 Code validation
│   │
│   ├── config.py         # Configuration ✅
│   └── database.py       # Database setup ✅
│
├── tests/                # Test suite 🔄 (Partial coverage)
│   ├── test_physics.py   # ✅ Comprehensive
│   ├── test_track.py     # ✅ Comprehensive
│   └── test_health.py    # ✅ Basic
└── main.py               # Application entry point ✅
```

### Implementation Status Summary

| Milestone | Components | Status |
|-----------|-----------|--------|
| M1: Foundation | Core physics, track generation, rendering | ✅ Complete |
| M2: Racing | Collisions, checkpoints, surfaces, HUD | 🔄 70% Complete |
| M3: Bot Framework | RestrictedPython sandbox, bot API | 📋 Planned |
| M4: Multiplayer | WebSocket (basic), state sync | 🔄 30% Complete |
| M5: Progression | User system, garage, database models | 📋 Planned |

### Game Engine

The game engine runs at a fixed tick rate (default: 60 Hz) and manages:

1. **Physics Simulation**: Position, velocity, acceleration, friction, collisions
2. **Stage State**: Surface types, boundaries, checkpoints, start and finish positions
3. **Race State**: Checkpoint progress, car positions, timing
4. **Bot Execution**: Calling bot code and processing actions

#### Physics Model

```
Car State:
- position (x, y)
- velocity (vx, vy)
- heading (angle in radians)
- angular_velocity
- current_surface

Each tick:
1. Apply surface friction coefficient
2. Process inputs (accelerate, brake, turn)
3. Calculate new velocity with drift physics
4. Detect collisions (elastic bouncing)
5. Apply off-track slowdown penalty
6. Update position
```

#### Drift Physics

Drift is modelled using a grip coefficient that varies by:
- Surface type (asphalt > gravel > ice)
- Car upgrades (grip stat)
- Current speed (less grip at higher speeds)

When grip is exceeded, the car slides with reduced control.

### Bot Runtime

User Python code executes in a RestrictedPython sandbox with:

**Allowed**:
- Basic Python operations
- Math functions
- Bot state storage (persistent dict)

**Blocked**:
- File system access
- Network access
- System calls
- Imports (except whitelisted)
- Infinite loops (execution timeout)

#### Bot Lifecycle

```
1. Bot code loaded and validated
2. Bot instance created (constructor called)
3. Each tick:
   a. Build sensor state (fog of war applied)
   b. Call bot.on_tick(state) with timeout
   c. Validate returned actions
   d. Apply actions to car
4. Event callbacks (on_collision, on_checkpoint, on_finish, etc.)
5. Bot state persisted after race
```

### Database Schema

```sql
-- Users
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    points INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Cars (user garage)
CREATE TABLE cars (
    id INTEGER PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    car_type TEXT NOT NULL,
    name TEXT,
    -- Upgrade stats
    top_speed INTEGER DEFAULT 0,
    acceleration INTEGER DEFAULT 0,
    grip INTEGER DEFAULT 0,
    braking INTEGER DEFAULT 0,
    nitro_capacity INTEGER DEFAULT 2,
    nitro_duration INTEGER DEFAULT 100,
    handling INTEGER DEFAULT 0,
    weight INTEGER DEFAULT 0,
    -- Metadata
    unlocked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Bot code
CREATE TABLE bots (
    id INTEGER PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    name TEXT NOT NULL,
    code TEXT NOT NULL,
    version INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Bot persistent state
CREATE TABLE bot_state (
    bot_id INTEGER PRIMARY KEY REFERENCES bots(id),
    state_json TEXT
);

-- Race results
CREATE TABLE race_results (
    id INTEGER PRIMARY KEY,
    race_id TEXT NOT NULL,
    user_id INTEGER REFERENCES users(id),
    car_id INTEGER REFERENCES cars(id),
    bot_id INTEGER REFERENCES bots(id),
    position INTEGER,
    stage_time REAL,
    dnf BOOLEAN DEFAULT FALSE,
    points_earned INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## Frontend Architecture

### Technology Stack

- **Framework**: React 18
- **Rendering**: HTML5 Canvas (2D)
- **State Management**: React Context + useReducer
- **Code Editor**: Monaco Editor
- **Communication**: WebSocket (native API)

### Component Structure

```
frontend/src/
├── components/           # UI Components 🔄
│   ├── Layout.tsx        # ✅ Navigation and layout
│   ├── RaceHUD.tsx       # ✅ Race progress display
│   ├── lobby/            # 📋 Race lobby (planned M4)
│   ├── garage/           # 📋 Car selection (planned M5)
│   ├── leaderboard/      # 📋 Rankings (planned M5)
│   └── auth/             # 📋 Login, registration (planned M5)
│
├── game/                 # Game Engine ✅
│   ├── GameCanvas.tsx    # ✅ Main rendering component
│   ├── renderer.ts       # ✅ Canvas drawing with camera system
│   ├── physics.ts        # ✅ Car physics simulation
│   ├── types.ts          # ✅ TypeScript interfaces
│   ├── useGameLoop.ts    # ✅ Fixed timestep game loop
│   ├── useKeyboardInput.ts # ✅ Keyboard handling
│   ├── trackUtils.ts     # ✅ Track collision/surface detection
│   └── checkpointUtils.ts # ✅ Checkpoint detection
│
├── editor/               # Bot Editor 📋 (Planned M3)
│   └── .gitkeep          # 📋 Monaco editor integration planned
│
├── pages/                # Application Pages 🔄
│   ├── Home.tsx          # ✅ Landing page
│   ├── Race.tsx          # ✅ Single-player mode
│   ├── MultiplayerRace.tsx # ✅ Multiplayer mode
│   └── Editor.tsx        # 📋 Placeholder (Monaco not integrated)
│
├── services/             # API Clients ✅
│   ├── trackApi.ts       # ✅ Track generation API
│   └── gameWebSocket.ts  # ✅ WebSocket with reconnection
│
└── App.tsx               # ✅ React Router setup
```

### Frontend Implementation Status

| Feature | Status | Notes |
|---------|--------|-------|
| Canvas Rendering | ✅ Complete | Track, cars, obstacles, checkpoints |
| Physics Engine | ✅ Complete | Synchronized with backend config |
| Keyboard Input | ✅ Complete | WASD + arrows + space |
| WebSocket Client | ✅ Complete | Reconnection logic included |
| Single-Player Mode | ✅ Complete | Local physics simulation |
| Multiplayer Mode | 🔄 Functional | Basic state sync working |
| Race HUD | ✅ Complete | Checkpoint progress, timer, warnings |
| Monaco Editor | 📋 Planned | For M3 bot programming |
| User Auth UI | 📋 Planned | For M5 progression system |

### Rendering Pipeline

1. Server sends game state via WebSocket (~20 Hz)
2. Client interpolates between states for smooth 60 FPS rendering
3. Canvas renders: track, cars, effects, UI overlay
4. Debug mode overlays: bot vision cones, velocity vectors

## Communication Protocol

### WebSocket Messages

**Client → Server**:
```json
{"type": "input", "actions": {"accelerate": true, "turn_left": false, ...}}
{"type": "join_race", "race_id": "abc123", "car_id": 1, "bot_id": null}
{"type": "ready"}
```

**Server → Client**:
```json
{"type": "game_state", "tick": 1234, "cars": [...], "race_info": {...}}
{"type": "race_start", "countdown": 3}
{"type": "race_end", "results": [...]}
{"type": "error", "message": "..."}
```

## Configuration

Server-side configuration in `config.py`:

```python
class Settings:
    # Server
    HOST = "0.0.0.0"
    PORT = 8000
    MAX_CONCURRENT_PLAYERS = 8

    # Game
    TICK_RATE = 60  # Hz
    BOT_TICK_RATE = 20  # Hz (bot called every 3rd tick)

    # Stage generation
    STAGE_MIN_LENGTH = 1000  # units
    STAGE_MAX_LENGTH = 3000  # units

    # Bot sandbox
    BOT_MEMORY_LIMIT_MB = 50
    BOT_EXECUTION_TIMEOUT_MS = 10

    # Database
    DATABASE_URL = "sqlite:///./coderally.db"
```

### Configuration API ✅

Physics constants are exposed via REST API for frontend synchronization:

**GET /config/physics**
```json
{
  "MAX_SPEED": 300.0,
  "ACCELERATION": 250.0,
  "BRAKE_FORCE": 250.0,
  "DRAG_COEFFICIENT": 0.5,
  "TURN_RATE": 4.5,
  ...
}
```

This ensures frontend and backend physics remain synchronized, critical for
multiplayer mode where server is authoritative.

## Security Considerations

1. **Bot Sandboxing**: RestrictedPython prevents malicious code
2. **Input Validation**: All client inputs validated server-side
3. **Rate Limiting**: WebSocket message rate limits
4. **Authentication**: Password hashing with bcrypt
5. **No Direct DB Access**: All queries through ORM

## Future Considerations

The architecture supports future additions:
- Cloud deployment (containerised)
- PostgreSQL migration (change connection string)
- OAuth integration (add providers to auth service)
- Replay system (log game states to DB)
- Spectator scaling (separate WebSocket channels)
