# CodeRally API Reference

Complete reference for CodeRally's REST and WebSocket APIs.

## Base URL

```
Development: http://localhost:8000
Production: https://your-domain.com/api
```

## Table of Contents

- [Authentication](#authentication) (Planned M5)
- [Health Endpoints](#health-endpoints)
- [Configuration Endpoints](#configuration-endpoints)
- [Track Endpoints](#track-endpoints)
- [Game WebSocket](#game-websocket)
- [Error Responses](#error-responses)

---

## Authentication

> **Status**: 📋 Planned for M5 (Progression)

Future authentication endpoints will include:
- `POST /auth/register` - Create new user account
- `POST /auth/login` - Authenticate and get session token
- `POST /auth/logout` - Invalidate session
- `GET /auth/me` - Get current user info

---

## Health Endpoints

### GET /health

Basic health check endpoint.

**Response: 200 OK**

```json
{
  "status": "healthy",
  "database": "connected"
}
```

**Example:**

```bash
curl http://localhost:8000/health
```

---

### GET /health/ready

Readiness probe for deployment orchestration (Kubernetes, Docker Swarm).

**Response: 200 OK**

```json
{
  "status": "ready"
}
```

**Example:**

```bash
curl http://localhost:8000/health/ready
```

---

## Configuration Endpoints

### GET /config/physics

Get physics configuration parameters used by the game engine.

**Purpose**: Ensures frontend can synchronize physics constants with backend for consistent multiplayer behavior.

**Response: 200 OK**

```json
{
  "MAX_SPEED": 300.0,
  "ACCELERATION": 250.0,
  "BRAKE_FORCE": 250.0,
  "DRAG_COEFFICIENT": 0.5,
  "TURN_RATE": 4.5,
  "MIN_TURN_SPEED": 1.0,
  "TURN_ACCELERATION": 20.0,
  "THROTTLE_RESPONSE": 20.0,
  "GRIP_ASPHALT": 1.0,
  "GRIP_WET": 0.7,
  "GRIP_GRAVEL": 0.5,
  "GRIP_ICE": 0.25,
  "DRIFT_THRESHOLD": 0.8,
  "DRIFT_RECOVERY_RATE": 15.0,
  "OFF_TRACK_SPEED_MULTIPLIER": 0.5,
  "OFF_TRACK_GRIP_MULTIPLIER": 0.3,
  "COLLISION_ELASTICITY": 0.7,
  "COLLISION_MIN_SPEED": 5.0,
  "CAR_RADIUS": 10.0
}
```

**Example:**

```bash
curl http://localhost:8000/config/physics
```

```javascript
// Frontend usage
const physicsConfig = await fetch('/config/physics').then(r => r.json());
```

---

### GET /config/game

Get game configuration parameters.

**Response: 200 OK**

```json
{
  "TICK_RATE": 60,
  "BOT_TICK_RATE": 20,
  "MAX_CARS": 8,
  "COUNTDOWN_SECONDS": 3,
  "STAGE_WIDTH": 160
}
```

**Example:**

```bash
curl http://localhost:8000/config/game
```

---

## Track Endpoints

### POST /tracks/generate

Generate a procedural rally stage track.

**Request Body:**

```json
{
  "difficulty": "medium",
  "seed": 12345
}
```

**Parameters:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `difficulty` | string | No | Difficulty level: `"easy"`, `"medium"`, or `"hard"`. Default: `"medium"` |
| `seed` | integer | No | Random seed for reproducible generation. Default: random |

**Response: 200 OK**

```json
{
  "segments": [
    {
      "start": {
        "x": 0,
        "y": 0,
        "width": 160,
        "surface": "asphalt"
      },
      "end": {
        "x": 200,
        "y": 50,
        "width": 160,
        "surface": "asphalt"
      },
      "control1": [66.67, 16.67],
      "control2": [133.33, 33.33]
    }
    // ... more segments
  ],
  "checkpoints": [
    {
      "position": [200, 50],
      "angle": 0.785,
      "width": 160,
      "index": 0
    }
    // ... more checkpoints
  ],
  "start_position": [0, 0],
  "start_heading": 0,
  "finish_position": [2000, 500],
  "finish_heading": 1.57,
  "total_length": 2500.0,
  "is_looping": false,
  "containment": {
    "left_points": [[x, y], ...],
    "right_points": [[x, y], ...]
  },
  "obstacles": [
    {
      "position": [300, 100],
      "radius": 15.0,
      "type": "rock"
    }
    // ... more obstacles
  ]
}
```

**Track Structure:**

- **segments**: Array of Bezier curve segments defining the track path
  - Straight segments have no `control1`/`control2` fields
  - Curved segments use cubic Bezier curves
- **checkpoints**: Progress markers placed along the track
- **start_position/heading**: Where cars start the race
- **finish_position/heading**: Where the finish line is located
- **is_looping**: `false` for rally stages (point-to-point), `true` for circuits (future)
- **containment**: Outer boundary walls that cars collide with
- **obstacles**: Off-road obstacles (rocks, trees, buildings)

**Example:**

```bash
curl -X POST http://localhost:8000/tracks/generate \
  -H "Content-Type: application/json" \
  -d '{"difficulty": "hard", "seed": 42}'
```

```javascript
// Frontend usage
const track = await fetch('/tracks/generate', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ difficulty: 'medium', seed: 12345 })
}).then(r => r.json());
```

---

## Game WebSocket

### WS /game/ws

Real-time multiplayer game connection.

**Connection:**

```javascript
const ws = new WebSocket('ws://localhost:8000/game/ws');

ws.onopen = () => {
  console.log('Connected to game server');
};

ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  handleGameMessage(message);
};

ws.onerror = (error) => {
  console.error('WebSocket error:', error);
};

ws.onclose = () => {
  console.log('Disconnected from game server');
};
```

---

### Client → Server Messages

#### join

Join a game session (or create new session).

**Format:**

```json
{
  "type": "join",
  "session_id": "optional-session-id",
  "player_name": "Player 1"
}
```

**Fields:**

- `session_id` (optional): ID of existing session to join. If omitted, creates new session.
- `player_name`: Display name for the player

---

#### input

Send player input actions.

**Format:**

```json
{
  "type": "input",
  "actions": {
    "accelerate": true,
    "brake": false,
    "turn_left": false,
    "turn_right": true,
    "use_nitro": false
  }
}
```

**Actions:**

All fields are booleans:
- `accelerate`: Apply forward thrust
- `brake`: Apply brakes
- `turn_left`: Rotate counter-clockwise
- `turn_right`: Rotate clockwise
- `use_nitro`: Activate nitro boost (if available)

**Rate Limit**: Max 30 messages per second per client

---

### Server → Client Messages

#### connected

Confirmation of successful connection.

**Format:**

```json
{
  "type": "connected",
  "session_id": "abc123",
  "player_id": 0
}
```

**Fields:**

- `session_id`: Unique session identifier
- `player_id`: Your player index in this game

---

#### track_data

Track information sent once when joining.

**Format:**

```json
{
  "type": "track_data",
  "track": {
    // ... full track object (same structure as POST /tracks/generate)
  }
}
```

---

#### game_state

Game state update (sent at ~20 Hz during race).

**Format:**

```json
{
  "type": "game_state",
  "tick": 1234,
  "race_status": "racing",
  "cars": [
    {
      "player_id": 0,
      "position": {"x": 150.5, "y": 75.2},
      "velocity": {"x": 120.0, "y": 30.0},
      "heading": 0.785,
      "angular_velocity": 0.1,
      "is_drifting": false,
      "drift_angle": 0.0,
      "throttle": 0.8,
      "is_off_track": false,
      "current_checkpoint": 2,
      "finished": false
    }
    // ... more cars
  ],
  "race_info": {
    "status": "racing",
    "start_time": 1702825200.5,
    "countdown_remaining": 0.0,
    "finish_time": null,
    "elapsed_time": 45.5
  }
}
```

**Race Status Values:**

- `"waiting"`: Waiting for players
- `"countdown"`: Pre-race countdown
- `"racing"`: Race in progress
- `"finished"`: Race ended

**Car State Fields:**

- `player_id`: Player identifier
- `position`: Car position (x, y)
- `velocity`: Velocity vector (vx, vy)
- `heading`: Direction car is facing (radians, 0 = right, π/2 = up)
- `angular_velocity`: Rate of rotation (radians/second)
- `is_drifting`: Whether car is currently drifting
- `drift_angle`: Angle between heading and velocity direction
- `throttle`: Current throttle level (0-1)
- `is_off_track`: Whether car is off the track
- `current_checkpoint`: Next checkpoint index to reach
- `finished`: Whether car has crossed the finish line

---

#### race_start

Race countdown has started.

**Format:**

```json
{
  "type": "race_start",
  "countdown": 3
}
```

**Note**: This message is sent when the race countdown begins. The countdown value is also included in the regular `game_state` messages via the `race_info.countdown_remaining` field.

---

#### checkpoint_passed

Player passed a checkpoint.

**Format:**

```json
{
  "type": "checkpoint_passed",
  "player_id": 0,
  "checkpoint_index": 2,
  "split_time": 23.5
}
```

**Fields:**

- `player_id`: Which player passed the checkpoint
- `checkpoint_index`: Index of checkpoint passed
- `split_time`: Time since race start (seconds)

---

#### race_end

Race has ended.

**Format:**

```json
{
  "type": "race_end",
  "results": [
    {
      "player_id": 0,
      "player_name": "Player 1",
      "position": 1,
      "finish_time": 125.5,
      "dnf": false
    },
    {
      "player_id": 1,
      "player_name": "Player 2",
      "position": 2,
      "finish_time": 130.2,
      "dnf": false
    }
  ]
}
```

**Result Fields:**

- `position`: Final race position (1st, 2nd, etc.)
- `finish_time`: Total stage time in seconds
- `dnf`: Did Not Finish (if true, player didn't complete the stage)

---

#### error

Error message from server.

**Format:**

```json
{
  "type": "error",
  "message": "Invalid session ID"
}
```

---

### WebSocket Example (Complete)

```javascript
class GameClient {
  constructor(wsUrl) {
    this.ws = new WebSocket(wsUrl);
    this.sessionId = null;
    this.playerId = null;

    this.ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      this.handleMessage(msg);
    };
  }

  handleMessage(msg) {
    switch (msg.type) {
      case 'connected':
        this.sessionId = msg.session_id;
        this.playerId = msg.player_id;
        console.log(`Connected as player ${this.playerId}`);
        break;

      case 'track_data':
        this.loadTrack(msg.track);
        break;

      case 'game_state':
        this.updateGameState(msg);
        break;

      case 'checkpoint_passed':
        console.log(`Player ${msg.player_id} passed checkpoint ${msg.checkpoint_index}`);
        break;

      case 'race_end':
        this.showResults(msg.results);
        break;

      case 'error':
        console.error('Server error:', msg.message);
        break;
    }
  }

  join(sessionId = null, playerName = 'Player') {
    this.ws.send(JSON.stringify({
      type: 'join',
      session_id: sessionId,
      player_name: playerName
    }));
  }

  sendInput(actions) {
    this.ws.send(JSON.stringify({
      type: 'input',
      actions: actions
    }));
  }
}

// Usage
const client = new GameClient('ws://localhost:8000/game/ws');
client.join(null, 'Alice');

// Send input (called every frame based on keyboard state)
setInterval(() => {
  client.sendInput({
    accelerate: keys.w || keys.ArrowUp,
    brake: keys.s || keys.ArrowDown,
    turn_left: keys.a || keys.ArrowLeft,
    turn_right: keys.d || keys.ArrowRight,
    use_nitro: keys.Space
  });
}, 50); // 20 Hz
```

---

## Error Responses

### HTTP Errors

**400 Bad Request**

```json
{
  "detail": "Invalid difficulty level. Must be 'easy', 'medium', or 'hard'."
}
```

**404 Not Found**

```json
{
  "detail": "Session not found"
}
```

**500 Internal Server Error**

```json
{
  "detail": "An internal error occurred"
}
```

---

### WebSocket Errors

**Invalid Message Format**

```json
{
  "type": "error",
  "message": "Invalid message format"
}
```

**Session Full**

```json
{
  "type": "error",
  "message": "Session is full (max 8 players)"
}
```

**Rate Limit Exceeded**

```json
{
  "type": "error",
  "message": "Too many input messages. Max 30 per second."
}
```

---

## Rate Limits

| Endpoint | Limit | Window |
|----------|-------|--------|
| GET /tracks/generate | 100 requests | 1 minute |
| WebSocket input messages | 30 messages | 1 second |

---

## Future Endpoints (Planned)

### M3: Bot Framework

- `POST /bots` - Upload bot code
- `GET /bots/{id}` - Get bot details
- `PUT /bots/{id}` - Update bot code
- `DELETE /bots/{id}` - Delete bot
- `POST /bots/{id}/test` - Test bot in sandbox

### M5: Progression

- `GET /garage` - List user's cars
- `POST /garage/cars` - Create/unlock car
- `PUT /garage/cars/{id}` - Upgrade car
- `GET /leaderboard` - Global leaderboard
- `GET /users/{id}/stats` - User statistics

### M6: Championship

- `GET /championships` - List championships
- `POST /championships/{id}/join` - Join championship
- `GET /championships/{id}/standings` - View standings

---

## API Versioning

Currently: **v1** (implicit, no version prefix)

Future versions will use URL prefix: `/v2/endpoint`

---

## OpenAPI Documentation

Interactive API documentation is available at:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

These docs are auto-generated by FastAPI and always up-to-date.

---

## Client Libraries

### Official

- JavaScript/TypeScript: Built into frontend (`src/services/`)

### Community

None yet. Contributions welcome!

---

## Support

- **Issues**: https://github.com/ettoreferranti/code-rally/issues
- **Documentation**: https://github.com/ettoreferranti/code-rally/tree/main/docs

---

## Changelog

### v0.1.0 (Current)

- ✅ Health endpoints
- ✅ Configuration endpoints
- ✅ Track generation
- ✅ Game WebSocket (basic multiplayer)

### v0.2.0 (Planned - M3)

- 📋 Bot management endpoints
- 📋 Bot testing/validation

### v0.3.0 (Planned - M5)

- 📋 User authentication
- 📋 Garage management
- 📋 Leaderboards
