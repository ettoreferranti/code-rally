# CodeRally - Development Guide for Claude

## Project Overview

CodeRally is a top-down 2D racing game where players can race using keyboard controls or write Python bots to compete autonomously. Think "Robocode meets rally racing".

**Repository**: https://github.com/ettoreferranti/code-rally
**Owner**: Ettore Ferranti (@ettoreferranti)

## Tech Stack

### Backend
- **Framework**: FastAPI (Python 3.11+)
- **Database**: SQLite with SQLAlchemy ORM
- **WebSocket**: FastAPI WebSocket for real-time game state
- **Bot Sandbox**: RestrictedPython for safe user code execution
- **Testing**: pytest (106 tests: unit, integration, regression, end-to-end)

### Frontend
- **Framework**: React 18
- **Rendering**: HTML5 Canvas (2D)
- **Code Editor**: Monaco Editor
- **State Management**: React Context + useReducer
- **Build Tool**: Vite
- **Testing**: Vitest + React Testing Library (5+ tests: component, integration)

## Project Structure

```
code-rally/
├── backend/
│   ├── app/
│   │   ├── api/           # FastAPI routes and WebSocket handlers
│   │   ├── core/          # Game engine, physics, track generation
│   │   ├── models/        # SQLAlchemy database models
│   │   ├── services/      # Business logic layer
│   │   ├── bot_runtime/   # RestrictedPython sandbox
│   │   └── config.py      # Server configuration
│   ├── tests/
│   ├── requirements.txt
│   └── main.py
├── frontend/
│   ├── src/
│   │   ├── components/    # React UI components
│   │   ├── game/          # Canvas rendering, game loop
│   │   ├── editor/        # Monaco code editor
│   │   └── services/      # API and WebSocket clients
│   ├── public/
│   └── package.json
├── docs/
│   ├── architecture.md    # System architecture
│   ├── bot-api.md         # Bot programming guide
│   └── requirements.md    # Full requirements spec
└── CLAUDE.md              # This file
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

## Testing Requirements

### Backend Tests (106 tests)

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

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Access at http://localhost:5173

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
| `backend/app/config.py` | All game parameters |
| `backend/app/core/physics.py` | Physics simulation |
| `backend/app/core/engine.py` | Main game loop |
| `backend/app/bot_runtime/sandbox.py` | Bot execution |
| `frontend/src/game/renderer.js` | Canvas rendering |
| `frontend/src/game/input.js` | Keyboard handling |

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
