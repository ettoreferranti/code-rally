# CodeRally 🏎️

A programmable racing game where you code your own AI drivers — in Python or as a locally-hosted LLM.

## Overview

CodeRally is a top-down 2D racing game inspired by Group B rally championships. It supports three kinds of drivers in any lobby:

- **Human** — race with the keyboard.
- **Python bot** — write a `BaseBot` subclass in the in-browser editor; runs sandboxed via RestrictedPython.
- **LLM bot** — a local language model (Apple-Silicon MLX) drives via a two-tier strategist/controller architecture with a per-bot system prompt.

The app has two main areas:

- **Play** (`/lobbies`) — browse / create a lobby, add bots from your library, race.
- **Tinker with bots** (`/tinker`) — your unified bot library: list, edit, delete, create either kind.

## Features

- **Simulation-style physics** with realistic drifting and four surface types (asphalt, gravel, ice, wet).
- **Procedurally generated tracks** with checkpoints, boundaries, obstacles, and varying surfaces.
- **Programmable bots** — Python sandbox OR local-LLM strategist with editable system prompt.
- **Multiplayer lobbies** — humans + bots of either kind in the same race; spectator mode supported.
- **Curated LLM model presets** — config-file driven (`backend/app/agents/llm_model_presets.json`), no code change to add a model.

## Tech Stack

- **Backend**: Python (FastAPI), SQLite (single-table unified `Bot` model), WebSocket.
- **Frontend**: React + Vite, HTML5 Canvas for rendering, Monaco for the Python editor.
- **Python bot runtime**: RestrictedPython (sandboxed).
- **LLM bot runtime**: MLX (Apple Silicon only, optional) — Qwen / Llama 4-bit models from `mlx-community`.

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

# Optional: LLM agents (Apple Silicon only)
# Required only if you want to race against LLM-driven cars.
# One-time install; the model itself (~1 GB) downloads from HuggingFace
# on first use and caches in ~/.cache/huggingface/.
pip install -r requirements-agents.txt

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
