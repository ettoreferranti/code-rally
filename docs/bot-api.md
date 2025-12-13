# CodeRally Bot API Guide

## Introduction

Welcome to CodeRally! This guide will teach you how to write Python code to control your racing car. Your bot competes against human players and other bots on procedurally generated point-to-point rally stages.

## Bot Structure

Every bot is a Python class with specific methods that the game engine calls:

```python
class MyBot:
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

Attempting restricted operations will cause your bot to be disqualified from the race.

## Example Bots

### Simple Follower

Follows the track using raycasts:

```python
class SimpleFollower:
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
class SurfaceAwareBot:
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

class CheckpointNavigator:
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

In Practice Mode, you can enable debug visualisation:

1. **Vision Rays**: See what your bot "sees"
2. **Velocity Vector**: Shows current movement direction
3. **Target Line**: Shows checkpoint navigation
4. **Console Output**: Use `print()` in your bot (visible in debug panel)

## Tips for Better Bots

1. **Start simple**: Get basic track following working first
2. **Use raycasts**: They are your most reliable sensors
3. **Respect surfaces**: Reduce speed on gravel and ice
4. **Learn the drift**: High-speed turns require early braking
5. **Save nitro**: Use it on straights, not in turns
6. **Study opponents**: Block or overtake strategically
7. **Iterate**: Use persistent memory to improve over time
