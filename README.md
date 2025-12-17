# CodeRally 🏎️

A programmable racing game where you code your own AI drivers in Python.

## Overview

CodeRally is a top-down 2D racing game inspired by Group B rally championships. What makes it unique is that you can program your own bot drivers using Python, competing against human players and other bots on procedurally generated tracks.

## Features

- **Simulation-style physics** with realistic drifting mechanics
- **Procedurally generated tracks** with varied surfaces (asphalt, gravel, ice, wet conditions)
- **Programmable bots** - Write Python code to control your car
- **Multiple car types** with upgradeable components
- **Multiplayer support** - Race against friends or bots
- **Championship mode** - Compete across multiple races

## Tech Stack

- **Backend**: Python (FastAPI), SQLite, WebSocket
- **Frontend**: React, Canvas/WebGL
- **Bot Runtime**: RestrictedPython (sandboxed execution)

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 18+
- Git

### Installation

```bash
# Clone the repository
git clone https://github.com/ettoreferranti/code-rally.git
cd code-rally

# Backend setup
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Frontend setup
cd ../frontend
npm install

# Run the application
# Terminal 1 - Backend
cd backend && uvicorn main:app --reload

# Terminal 2 - Frontend
cd frontend && npm run dev
```

## Documentation

- [Architecture](docs/architecture.md)
- [Bot API Guide](docs/bot-api.md)
- [Requirements](docs/requirements.md)

## Writing Your First Bot

```python
class MyBot:
    def __init__(self):
        self.name = "My First Bot"

    def on_tick(self, state):
        # state contains: car position, speed, heading, track info, opponents, etc.

        # Simple logic: accelerate and follow the track
        actions = {
            "accelerate": True,
            "brake": False,
            "turn_left": state.track.upcoming_turn == "left",
            "turn_right": state.track.upcoming_turn == "right",
            "use_nitro": False
        }
        return actions

    def on_collision(self, event):
        # React to collisions (with cars, obstacles, or boundaries)
        pass

    def on_checkpoint(self, checkpoint_index, split_time):
        # Called when passing each checkpoint
        print(f"Checkpoint {checkpoint_index} at {split_time:.2f}s")

    def on_finish(self, finish_time, final_position):
        # Called when crossing the finish line
        print(f"Finished in {final_position} place! Time: {finish_time:.2f}s")
```

See [Bot API Guide](docs/bot-api.md) for full documentation.

## License

MIT License - See LICENSE file for details.

## Contributing

Contributions welcome! Please check the GitHub issues for planned features.
