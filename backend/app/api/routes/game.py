"""
WebSocket API for real-time game state and multiplayer racing.
"""

import asyncio
import json
from typing import Dict, Set, Optional, Tuple
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from uuid import uuid4

from app.core.engine import GameEngine, PlayerInput
from app.core.track import TrackGenerator
from app.config import get_settings

router = APIRouter(prefix="/game", tags=["game"])

# Active game sessions (session_id -> GameEngine)
_game_sessions: Dict[str, GameEngine] = {}

# WebSocket connections (session_id -> set of WebSockets)
_connections: Dict[str, Set[WebSocket]] = {}


class ConnectionManager:
    """Manages WebSocket connections for multiplayer games."""

    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, session_id: str, player_id: str) -> None:
        """Accept a new WebSocket connection."""
        await websocket.accept()

        if session_id not in self.active_connections:
            self.active_connections[session_id] = set()

        self.active_connections[session_id].add(websocket)

    def disconnect(self, websocket: WebSocket, session_id: str) -> None:
        """Remove a WebSocket connection."""
        if session_id in self.active_connections:
            self.active_connections[session_id].discard(websocket)

            # Clean up empty sessions
            if not self.active_connections[session_id]:
                del self.active_connections[session_id]

    async def broadcast(self, message: dict, session_id: str) -> None:
        """Broadcast a message to all connections in a session."""
        if session_id not in self.active_connections:
            return

        # Convert message to JSON once
        json_message = json.dumps(message)

        # Send to all connected clients
        disconnected = []
        for connection in self.active_connections[session_id]:
            try:
                await connection.send_text(json_message)
            except Exception:
                # Mark for removal
                disconnected.append(connection)

        # Remove disconnected clients
        for connection in disconnected:
            self.disconnect(connection, session_id)


manager = ConnectionManager()


def get_or_create_session(session_id: Optional[str] = None, difficulty: str = "medium", seed: Optional[int] = None) -> Tuple[str, GameEngine]:
    """
    Get an existing game session or create a new one.

    Args:
        session_id: Existing session ID, or None to create new
        difficulty: Track difficulty for new sessions
        seed: Random seed for track generation

    Returns:
        Tuple of (session_id, GameEngine)
    """
    # Create new session
    if session_id is None or session_id not in _game_sessions:
        session_id = str(uuid4())

        # Generate track
        generator = TrackGenerator(seed=seed)
        track = generator.generate(difficulty=difficulty)

        # Create game engine
        engine = GameEngine(track)
        _game_sessions[session_id] = engine

        return session_id, engine

    # Return existing session
    return session_id, _game_sessions[session_id]


async def broadcast_game_state(session_id: str) -> None:
    """Broadcast current game state to all players in a session."""
    if session_id not in _game_sessions:
        return

    engine = _game_sessions[session_id]
    state = engine.get_state_snapshot()

    message = {
        'type': 'game_state',
        'data': state
    }

    await manager.broadcast(message, session_id)


async def state_broadcaster(session_id: str, update_rate: int = 60) -> None:
    """
    Background task to broadcast game state at regular intervals.

    Args:
        session_id: Game session to broadcast
        update_rate: Updates per second (Hz)
    """
    interval = 1.0 / update_rate

    while session_id in _game_sessions and session_id in manager.active_connections:
        await broadcast_game_state(session_id)
        await asyncio.sleep(interval)


@router.websocket("/ws")
async def game_websocket(
    websocket: WebSocket,
    session_id: Optional[str] = Query(default=None),
    difficulty: str = Query(default="medium"),
    seed: Optional[int] = Query(default=None)
):
    """
    WebSocket endpoint for real-time multiplayer racing.

    Players send inputs and receive game state updates.

    Message format (client -> server):
    {
        "type": "input",
        "data": {
            "accelerate": bool,
            "brake": bool,
            "turn_left": bool,
            "turn_right": bool,
            "nitro": bool
        }
    }

    Message format (server -> client):
    {
        "type": "game_state",
        "data": {
            "tick": int,
            "race_info": {...},
            "players": {...}
        }
    }
    """
    # Generate unique player ID
    player_id = str(uuid4())

    # Get or create game session
    session_id, engine = get_or_create_session(session_id, difficulty, seed)

    # Connect player
    await manager.connect(websocket, session_id, player_id)

    # Add player to game
    engine.add_player(player_id)

    # Start game loop if not already running
    if not engine._running:
        await engine.start_loop()

        # Start state broadcaster
        asyncio.create_task(state_broadcaster(session_id))

    try:
        # Send initial connection success message
        await websocket.send_json({
            'type': 'connected',
            'data': {
                'session_id': session_id,
                'player_id': player_id,
                'track': {
                    'segments': [
                        {
                            'start': {
                                'x': seg.start.x,
                                'y': seg.start.y,
                                'width': seg.start.width,
                                'surface': seg.start.surface.value if hasattr(seg.start.surface, 'value') else seg.start.surface
                            },
                            'end': {
                                'x': seg.end.x,
                                'y': seg.end.y,
                                'width': seg.end.width,
                                'surface': seg.end.surface.value if hasattr(seg.end.surface, 'value') else seg.end.surface
                            },
                            'control1': list(seg.control1) if seg.control1 else None,
                            'control2': list(seg.control2) if seg.control2 else None,
                        }
                        for seg in engine.state.track.segments
                    ],
                    'checkpoints': [
                        {
                            'position': list(cp.position),
                            'angle': cp.angle,
                            'width': cp.width
                        }
                        for cp in engine.state.track.checkpoints
                    ],
                    'start_position': list(engine.state.track.start_position),
                    'start_heading': engine.state.track.start_heading,
                    'obstacles': [
                        {
                            'position': list(obs.position),
                            'radius': obs.radius,
                            'type': obs.type
                        }
                        for obs in (engine.state.track.obstacles or [])
                    ]
                }
            }
        })

        # Listen for player inputs
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            message = json.loads(data)

            if message['type'] == 'input':
                # Update player input
                input_data = message['data']
                player_input = PlayerInput(
                    accelerate=input_data.get('accelerate', False),
                    brake=input_data.get('brake', False),
                    turn_left=input_data.get('turn_left', False),
                    turn_right=input_data.get('turn_right', False),
                    nitro=input_data.get('nitro', False)
                )
                engine.update_player_input(player_id, player_input)

            elif message['type'] == 'start_race':
                # Start race countdown
                engine.start_race()

    except WebSocketDisconnect:
        # Player disconnected
        manager.disconnect(websocket, session_id)
        engine.remove_player(player_id)

        # If no players left, stop the engine and clean up
        if not engine.state.players:
            await engine.stop_loop()
            if session_id in _game_sessions:
                del _game_sessions[session_id]


@router.get("/sessions")
async def list_sessions():
    """List active game sessions."""
    return {
        'sessions': [
            {
                'session_id': session_id,
                'player_count': len(engine.state.players),
                'status': engine.state.race_info.status.value
            }
            for session_id, engine in _game_sessions.items()
        ]
    }
