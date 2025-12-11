# CodeRally Requirements Specification

## Project Vision

CodeRally is a top-down 2D racing game that combines classic rally racing with programmable AI. Players can race using keyboard controls or write Python code to create autonomous racing bots, competing against other humans and bots on procedurally generated tracks.

## Core Features

### 1. Game Physics (Simulation-Style)

- **Realistic momentum and inertia**
- **Drift mechanics**: Cars can oversteer and drift through corners
- **Surface-dependent grip**: Different friction coefficients per surface
- **Elastic collisions**: Cars bounce off each other and boundaries
- **Off-track penalty**: Reduced speed when driving off the track
- **Discrete input model**: Binary accelerate/brake/turn controls

### 2. Track System

- **Procedural generation**: Each race has a unique track
- **Surface types**:
  - Asphalt (high grip)
  - Gravel (medium grip)
  - Ice (low grip)
  - Wet asphalt (reduced grip)
- **Dynamic obstacles**: Objects on track to avoid
- **Checkpoint system**: For lap counting and validation

### 3. Car System

#### Base Car Types
- **Speedster**: High top speed, lower acceleration
- **Tank**: Heavy, good collision resistance, slower
- **Balanced**: Average all stats

#### Upgrade Dimensions
- Top speed
- Acceleration
- Grip
- Braking power
- Nitro capacity (default: 2)
- Nitro duration
- Handling/turning radius
- Weight

#### Upgrade System
- Budget-based allocation
- Points earned from race results
- Each upgrade has cost

### 4. Power-ups

- **Nitro boost**: Temporary speed increase
- Tied to car upgrades (capacity, duration)
- No combat items (pure racing)

### 5. Bot Programming System

#### Code Editor
- In-browser Monaco editor
- Syntax highlighting
- Error display
- Template bots provided

#### Execution Model
- Hybrid tick/event-based
- `on_tick()` called ~20 Hz
- Event callbacks: `on_collision()`, `on_lap_complete()`
- Asynchronous execution

#### Sensor Data (with Fog of War)
**Own car**:
- Position (x, y)
- Heading (angle)
- Velocity vector
- Current speed
- Angular velocity
- Health (future)
- Nitro charges
- Current surface
- Off-track status

**Track info**:
- Upcoming track geometry (raycasts)
- Distance to boundaries
- Checkpoint positions
- Next turn direction/sharpness

**Opponents** (only nearby visible):
- Positions
- Velocities
- Headings

**Race state**:
- Lap count
- Position/ranking
- Time elapsed

#### Security (Sandbox)
- RestrictedPython execution
- No file/network access
- No system calls
- Whitelisted imports only (math)
- Execution timeout per tick
- Memory limit (configurable)

#### Persistence
- Bot code stored server-side
- Multiple versions per user
- Bot state persisted between races

### 6. Multiplayer

#### Race Configuration
- 1-8 cars per race (configurable)
- Mix of human and bot controlled
- All-bot races supported

#### Connection Model
- WebSocket real-time sync
- Server-authoritative state
- Desktop browser clients

### 7. Game Modes

- **Quick Race**: Single race, random track
- **Championship**: Series of races, cumulative points
- **Practice Mode**: Solo with debugging tools
- (Spectator mode inherently supported)

### 8. User System

#### Authentication
- Username/password
- Server-side storage
- Session management

#### Progression
- Points earned from races
- Unlock cars through play
- Starting car provided

#### Garage
- Store multiple cars
- Store multiple bot versions
- Assign bots to cars

#### Leaderboards
- Global points ranking
- Statistics tracking

### 9. Technical Requirements

#### Backend
- Python (FastAPI)
- SQLite database
- WebSocket support
- Server-authoritative game state

#### Frontend
- React
- HTML5 Canvas rendering
- Monaco code editor
- WebSocket client

#### Deployment
- Self-hosted (local PC)
- Single server instance
- Max 8 concurrent players (configurable)

### 10. Visual Style

- Minimalist 2D
- Top-down view
- Group B rally aesthetic inspiration
- Clear track/car distinction

## Non-Functional Requirements

### Performance
- 60 FPS rendering (client)
- 60 Hz physics tick (server)
- 20 Hz bot execution
- < 100ms latency tolerance

### Security
- Sandboxed code execution
- Input validation
- Password hashing

### Usability
- Tutorial/documentation for bot API
- Debug visualisation in practice mode
- Clear error messages

## Future Development (Not in Initial Scope)

Tagged for future implementation:

- Analogue controls (variable throttle/steering)
- Car damage system
- Track elevation changes
- Track shortcuts
- Combat items (shields, oil slicks, etc.)
- OAuth login (GitHub)
- Cloud hosting
- Race replay system
- Bot marketplace/sharing
- Mobile support
