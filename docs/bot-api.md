# CodeRally Bot API Guide

## Introduction

Welcome to CodeRally! This guide covers writing **Python bots** to
control your racing car. Bots live in your library under the
[Tinker page](/tinker) and can be added to any lobby alongside
humans and other bots.

CodeRally also supports a second kind of bot — **LLM bots**, driven
by a local language model with a custom system prompt — that
doesn't involve any Python code. See the [LLM Bots](#llm-bots) section
at the end of this doc for the gist.

Your bot competes against human players and other bots on procedurally
generated point-to-point rally stages.

## Bot Structure

Every Python bot is a class with specific methods that the game engine
calls.

**IMPORTANT**: All bots must inherit from `GuardedBotBase` or `BaseBot` to work in the sandbox environment.

```python
class MyBot(GuardedBotBase):  # or inherit from BaseBot
    def __init__(self):
        """Called once when your bot is loaded."""
        self.name = "My Bot Name"
        # Initialise any variables you need
        self.checkpoints_passed = 0

    def on_tick(self, state):
        """Called every game tick (~20 times per second).

        Args:
            state: GameState object with all sensor data

        Returns:
            dict: Actions to perform
        """
        actions = {
            "accelerate": True,
            "brake": False,
            "turn_left": False,
            "turn_right": False,
            "use_nitro": False
        }
        return actions

    def on_collision(self, event):
        """Called when your car collides with something.

        Args:
            event: CollisionEvent with collision details
        """
        pass

    def on_checkpoint(self, checkpoint_index, split_time):
        """Called when you pass a checkpoint.

        Args:
            checkpoint_index: Index of checkpoint passed (0, 1, 2...)
            split_time: Time in seconds since stage start
        """
        self.checkpoints_passed = checkpoint_index + 1

    def on_finish(self, finish_time, final_position):
        """Called when you cross the finish line.

        Args:
            finish_time: Total time in seconds for the stage
            final_position: Final race position (1st, 2nd, etc.)
        """
        pass
```

## Game State (Sensor Data)

The `state` object passed to `on_tick()` contains everything your bot can "see":

### Own Car Data (`state.car`)

| Property | Type | Description |
|----------|------|-------------|
| `position` | `(x, y)` | Your position on the track |
| `heading` | `float` | Direction facing (radians, 0 = right, π/2 = up) |
| `speed` | `float` | Current speed (units/second) |
| `velocity` | `(vx, vy)` | Velocity vector |
| `angular_velocity` | `float` | Rotation speed (radians/second) |
| `health` | `float` | Car health 0-100 (future feature) |
| `nitro_charges` | `int` | Remaining nitro uses |
| `nitro_active` | `bool` | Whether nitro is currently active |
| `current_surface` | `str` | Surface type: "asphalt", "gravel", "ice", "wet" |
| `off_track` | `bool` | Whether you are off the track |

### Track Information (`state.track`)

| Property | Type | Description |
|----------|------|-------------|
| `checkpoints` | `list` | List of checkpoint positions |
| `next_checkpoint` | `int` | Index of next checkpoint to reach |
| `distance_to_boundary_left` | `float` | Distance to left track edge |
| `distance_to_boundary_right` | `float` | Distance to right track edge |
| `upcoming_surface` | `str` | Surface type ahead |
| `upcoming_turn` | `str` | Next turn direction: "left", "right", "straight" |
| `turn_sharpness` | `float` | How sharp the upcoming turn is (0-1) |

### Raycasts (`state.rays`)

Your bot has 7 "vision rays" that detect obstacles and track boundaries:

```
        ray[2]  ray[1]  ray[0]
             \    |    /
              \   |   /
     ray[3] ───── CAR ───── (heading direction)
              /   |   \
             /    |    \
        ray[4]  ray[5]  ray[6]
```

Each ray returns:
```python
state.rays[0].distance    # Distance to obstacle (max 200 units)
state.rays[0].hit_type    # "boundary", "car", "obstacle", or None
```

### Opponents (`state.opponents`)

List of visible opponents (fog of war applies - only nearby cars):

```python
for opponent in state.opponents:
    opponent.position      # (x, y) position
    opponent.velocity      # (vx, vy) velocity
    opponent.heading       # Direction facing
    opponent.distance      # Distance from you
    opponent.relative_angle # Angle relative to your heading
```

### Race State (`state.race`)

| Property | Type | Description |
|----------|------|-------------|
| `current_checkpoint` | `int` | Index of next checkpoint to reach |
| `total_checkpoints` | `int` | Total checkpoints in stage |
| `position` | `int` | Your race position (1st, 2nd, etc.) |
| `total_cars` | `int` | Number of cars in race |
| `elapsed_time` | `float` | Stage time in seconds |
| `distance_to_finish` | `float` | Approximate distance to finish line |

## Actions

Return a dictionary with these boolean values:

| Action | Effect |
|--------|--------|
| `accelerate` | Apply forward thrust |
| `brake` | Apply brakes (slow down) |
| `turn_left` | Rotate counter-clockwise |
| `turn_right` | Rotate clockwise |
| `use_nitro` | Activate nitro boost (if available) |

**Note**: `accelerate` and `brake` can both be `False` (coasting) but having both `True` will prioritise braking. Similarly, `turn_left` and `turn_right` cancel each other out if both are `True`.

## Collision Events

The `on_collision(event)` method receives:

```python
event.other_type    # "car", "boundary", "obstacle"
event.impact_speed  # How fast the collision was
event.direction     # Angle of impact relative to your heading
event.other_id      # ID of other car (if car collision)
```

## Persistent State

Your bot can store data between races using `self.memory`:

```python
class MyBot:
    def __init__(self):
        self.name = "Learning Bot"
        # self.memory is automatically saved/loaded between races
        if not hasattr(self, 'memory'):
            self.memory = {}

        # Track statistics across stages
        if 'stages_completed' not in self.memory:
            self.memory['stages_completed'] = 0
            self.memory['best_time'] = float('inf')

    def on_tick(self, state):
        # Use historical data to improve
        pass

    def on_finish(self, finish_time, final_position):
        self.memory['stages_completed'] += 1
        if finish_time < self.memory['best_time']:
            self.memory['best_time'] = finish_time
```

## Restrictions

For security, your bot code cannot:

- Import most modules (only `math` is allowed)
- Access files or network
- Use infinite loops (10ms execution timeout per tick)
- Use more than 50MB memory
- Access system functions
- Use augmented assignment on **attributes** or **dictionary items**
  (`self.x += 1`, `dict[key] += 1`). RestrictedPython rejects these
  at compile time.

Augmented assignment on plain **local variables** (e.g. `count += 1`
where `count` was assigned earlier in the function) works fine.

**Note on Attribute / Dictionary Updates**: Instead of
`self.memory['count'] += 1`, use
`self.memory['count'] = self.memory['count'] + 1`.

Attempting restricted operations will cause your bot to be disqualified from the race.

## Example Bots

### Simple Follower

Follows the track using raycasts:

```python
class SimpleFollower(GuardedBotBase):
    def __init__(self):
        self.name = "Simple Follower"

    def on_tick(self, state):
        left_clear = state.rays[2].distance > 50
        right_clear = state.rays[4].distance > 50
        front_clear = state.rays[0].distance > 30

        return {
            "accelerate": front_clear,
            "brake": not front_clear,
            "turn_left": not left_clear and right_clear,
            "turn_right": not right_clear and left_clear,
            "use_nitro": False
        }
```

### Surface-Aware Racer

Adjusts driving style based on surface:

```python
class SurfaceAwareBot(GuardedBotBase):
    def __init__(self):
        self.name = "Surface Aware"
    
    def on_tick(self, state):
        surface = state.car.current_surface
        speed = state.car.speed
        
        # Slow down on slippery surfaces
        max_speed = {
            "asphalt": 100,
            "wet": 70,
            "gravel": 60,
            "ice": 40
        }.get(surface, 50)
        
        should_brake = speed > max_speed
        
        # Basic steering
        turn = self._calculate_turn(state)
        
        return {
            "accelerate": not should_brake,
            "brake": should_brake,
            "turn_left": turn < 0,
            "turn_right": turn > 0,
            "use_nitro": surface == "asphalt" and speed < 50
        }
    
    def _calculate_turn(self, state):
        # Negative = turn left, Positive = turn right
        left_dist = state.rays[2].distance
        right_dist = state.rays[4].distance
        return right_dist - left_dist
```

### Checkpoint Navigator

Uses checkpoint positions for optimal racing line:

```python
import math

class CheckpointNavigator(GuardedBotBase):
    def __init__(self):
        self.name = "Navigator"
    
    def on_tick(self, state):
        # Get next checkpoint
        checkpoints = state.track.checkpoints
        next_idx = state.track.next_checkpoint
        target = checkpoints[next_idx]
        
        # Calculate angle to target
        pos = state.car.position
        heading = state.car.heading
        
        dx = target[0] - pos[0]
        dy = target[1] - pos[1]
        target_angle = math.atan2(dy, dx)
        
        # Angle difference
        diff = target_angle - heading
        # Normalise to -π to π
        while diff > math.pi:
            diff -= 2 * math.pi
        while diff < -math.pi:
            diff += 2 * math.pi
        
        # Steering threshold
        threshold = 0.1
        
        return {
            "accelerate": True,
            "brake": abs(diff) > 0.5,  # Brake for sharp turns
            "turn_left": diff > threshold,
            "turn_right": diff < -threshold,
            "use_nitro": abs(diff) < 0.2 and state.car.speed < 80
        }
```

## Debugging Tips

- Create a **solo lobby** (just you, no other humans) and add your bot
  to it via the unified Add-to-lobby picker in the waiting room. That's
  the modern equivalent of the old "Practice Mode" — you can iterate
  on your bot without anyone else racing alongside.
- Bots can `print()` freely; output goes to the server console, not
  the browser. Watch your `uvicorn` log to see what your bot prints.
- The race HUD shows your bot's car like any other, with its name
  visible. Watch how it behaves to debug.

## Tips for Better Bots

1. **Start simple**: Get basic track following working first
2. **Use raycasts**: They are your most reliable sensors
3. **Respect surfaces**: Reduce speed on gravel and ice
4. **Learn the drift**: High-speed turns require early braking
5. **Save nitro**: Use it on straights, not in turns
6. **Study opponents**: Block or overtake strategically
7. **Iterate**: Use persistent memory to improve over time

## Technical Implementation

### Type Definitions

All bot API types are defined in `app/bot_runtime/types.py`:

```python
from app.bot_runtime import (
    BotGameState,      # Complete game state passed to on_tick()
    BotCarState,       # Your car's sensor data
    BotTrackState,     # Track information
    BotRaycast,        # Raycast sensor result
    BotOpponent,       # Opponent car data
    BotRaceState,      # Race progress
    BotActions,        # Actions to return from on_tick()
    CollisionEvent,    # Collision event data
    BaseBot,           # Base class for bots
)
```

### BaseBot Class

You can inherit from `BaseBot` for IDE autocomplete and type hints:

```python
from app.bot_runtime import BaseBot, BotGameState, BotActions

class MyBot(BaseBot):
    def __init__(self):
        super().__init__()
        self.name = "My Racing Bot"

    def on_tick(self, state: BotGameState) -> BotActions:
        # Your racing logic here
        return BotActions(accelerate=True)
```

### Immutability

All bot-facing data structures are **immutable** (frozen dataclasses). This prevents accidental state modification:

```python
# This will work:
speed = state.car.speed

# This will raise an error:
state.car.speed = 100  # FrozenInstanceError!
```

### Type Safety

All types include full type hints for IDE support:

```python
def on_tick(self, state: BotGameState) -> BotActions:
    # IDE will autocomplete these fields:
    position: Tuple[float, float] = state.car.position
    checkpoints: List[Tuple[float, float]] = state.track.checkpoints
    rays: List[BotRaycast] = state.rays

    # Type checker will catch errors:
    state.car.nitro_charges + state.car.speed  # OK: int + float
    state.car.position + state.car.heading     # Error: tuple + float

    return BotActions(accelerate=True, brake=False)
```

### Action Dictionary Format

If you prefer dictionaries, `BotActions` provides conversion methods:

```python
# Create from dict
actions_dict = {
    "accelerate": True,
    "turn_right": True,
}
actions = BotActions.from_dict(actions_dict)

# Convert to dict
actions_dict = actions.to_dict()
# Returns: {"accelerate": True, "brake": False, "turn_left": False, ...}
```

### Callback Signatures

Complete callback method signatures:

```python
class MyBot(BaseBot):
    def on_tick(self, state: BotGameState) -> BotActions:
        """Called ~20 times per second during race."""
        pass

    def on_collision(self, event: CollisionEvent) -> None:
        """Called when car collides with something."""
        pass

    def on_checkpoint(self, checkpoint_index: int, split_time: float) -> None:
        """Called when passing a checkpoint."""
        pass

    def on_finish(self, finish_time: float, final_position: int) -> None:
        """Called when crossing finish line."""
        pass

    def on_race_start(self) -> None:
        """Called when race countdown finishes (optional)."""
        pass

    def on_race_end(self) -> None:
        """Called when race ends for all players (optional)."""
        pass
```

### Memory Persistence

The `self.memory` dictionary is the canonical place to keep
per-race state. It survives across event callbacks within a single
race (e.g. counts accumulated in `on_checkpoint` are visible from
`on_tick`).

```python
class LearningBot(BaseBot):
    def __init__(self):
        super().__init__()
        self.name = "Learning Bot"

        # Initialise memory on first run within this race.
        if 'tick_count' not in self.memory:
            self.memory['tick_count'] = 0

    def on_tick(self, state):
        # Augmented assignment on dict items is forbidden by
        # RestrictedPython — use explicit get/set.
        self.memory['tick_count'] = self.memory['tick_count'] + 1
        return BotActions(accelerate=True)
```

**Note**: Memory is in-process only — it lives for the lifetime of
the bot instance (one race). There is currently no database-backed
state persistence between races; the bot is reinstantiated each time
it joins a new race. If you want persistent learning, that requires
adding a `bot_state` storage layer (not currently shipped).

## LLM Bots

In addition to Python bots, CodeRally supports **LLM-driven cars**
where a local Apple-Silicon-hosted language model decides the driving
strategy. You don't write code for these — you configure two things:

- a **model path** (chosen from a curated dropdown of MLX
  `mlx-community/...` models, or a free-text custom path), and
- a **driving strategy** prompt that describes how the bot drives
  (persona, risk appetite, surface heuristics).

You only write the strategy. The JSON I/O contract that the
controller needs to parse (Intent fields below) is held in an
invariant `PROTOCOL_PROMPT` that the server always appends on top of
your strategy — so a typo in your prompt can't accidentally break the
bot's I/O contract. See `backend/app/agents/llm_strategist.py::build_prompt`.

A new LLM bot in Tinker pre-fills the strategy with the default
racing persona (braking/apex/exit, surface adjustments, nitro and
tactical guidance) so you can tweak rather than start from scratch.

Architecturally the LLM bot uses a two-tier setup:

```
LLM Strategist (~1Hz async)            Deterministic Controller (20Hz sync)
    obs (text) → Intent JSON       →     reads latest Intent,
    {target_speed_kmh,                    emits steer / accel / brake
     racing_line_offset_m,                / nitro flags (the same
     aggression,                          PlayerInput that humans /
     use_nitro,                           Python bots emit)
     target_opponent_index,
     tactic}
```

Intent fields the strategist may emit:

| Field | Range | Meaning |
|-------|-------|---------|
| `target_speed_kmh` | 40–200 | Speed the controller targets next second. |
| `racing_line_offset_m` | -10 to 10 | Lateral offset from track centre (− left of track direction, + right). |
| `aggression` | 0.3–1.0 | Tightens steering/speed deadbands. |
| `use_nitro` | bool (default `false`) | Activate nitro this tick (controller gates on available charges). |
| `target_opponent_index` | `0`, `1`, or `null` (default `null`) | Index into the observation's opponent slots. |
| `tactic` | `"race"`, `"overtake"`, `"block"`, `"pit"` (default `"race"`) | Drives how the controller treats the targeted opponent. `block` uses the upcoming turn even without a target. |

The strategist's slow LLM call doesn't block the 20Hz tick — the
controller holds the last good Intent if a call is in-flight or fails.
LLM bots and Python bots compete in the same races, against each
other and against humans, with no special handling beyond the lobby
add-bot dispatch.

**Cold-start warmup.** The strategist needs an observation to
produce an intent, and the engine only feeds observations during
`RaceStatus.RACING`. To avoid the LLM driver starting from a
30 km/h fallback cruise while the others go full throttle,
`engine.start_agents` pre-feeds each LLM bot's strategist with the
start-position observation AND runs one synchronous warmup
generate during countdown. By green light, an Intent is already
cached, so the LLM driver hits the throttle on tick 0 just like
everyone else.

The observation the strategist receives is a fixed-shape text block
with terrain-aware fields: real `edge_left`/`edge_right` boundary
distances, `next_turn` direction + sharpness, `upcoming_surface`,
nitro state, race position, distance to finish, and (for each visible
opponent) a `closing`/`opening` descriptor. See
`backend/app/agents/observation.py::format_observation`.

To create one: open **Tinker → New bot → LLM bot**. Fill in the name,
pick a model from the dropdown (or paste a custom HuggingFace path),
and edit the driving strategy to taste. Then race it like any other
bot.

MLX is an Apple-Silicon-only optional dependency. Install it once
with `pip install -r backend/requirements-agents.txt`; without it,
LLM bots cannot be added to a lobby and the Add button will show a
clear error.
