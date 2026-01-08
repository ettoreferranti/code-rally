"""
WebSocket API for real-time game state and multiplayer racing.
"""

import asyncio
import json
import time
import logging
from typing import Dict, Set, Optional, Tuple
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from uuid import uuid4

from app.core.engine import GameEngine, PlayerInput, RaceStatus
from app.core.track import TrackGenerator
from app.core.bot_manager import BotError
from app.config import get_settings
from app.database import SessionLocal
from app.services import bot_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/game", tags=["game"])

# Active game sessions (session_id -> GameEngine)
_game_sessions: Dict[str, GameEngine] = {}

# WebSocket connections (session_id -> set of WebSockets)
_connections: Dict[str, Set[WebSocket]] = {}


class ConnectionManager:
    """Manages WebSocket connections for multiplayer games."""

    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        # Track connection metadata (last pong time, player info)
        self.connection_metadata: Dict[WebSocket, dict] = {}

    async def connect(self, websocket: WebSocket, session_id: str, player_id: str) -> None:
        """Accept a new WebSocket connection."""
        await websocket.accept()

        if session_id not in self.active_connections:
            self.active_connections[session_id] = set()

        self.active_connections[session_id].add(websocket)

        # Initialize connection metadata
        self.connection_metadata[websocket] = {
            'last_pong_time': time.time(),
            'player_id': player_id,
            'session_id': session_id
        }

    def disconnect(self, websocket: WebSocket, session_id: str) -> None:
        """Remove a WebSocket connection."""
        if session_id in self.active_connections:
            self.active_connections[session_id].discard(websocket)

            # Clean up empty sessions
            if not self.active_connections[session_id]:
                del self.active_connections[session_id]

        # Clean up metadata
        if websocket in self.connection_metadata:
            del self.connection_metadata[websocket]

    def update_pong_time(self, websocket: WebSocket) -> None:
        """Update last pong time for a connection."""
        if websocket in self.connection_metadata:
            self.connection_metadata[websocket]['last_pong_time'] = time.time()

    def get_last_pong_time(self, websocket: WebSocket) -> float:
        """Get last pong time for a connection."""
        if websocket in self.connection_metadata:
            return self.connection_metadata[websocket]['last_pong_time']
        return 0.0

    async def broadcast(self, message: dict, session_id: str) -> None:
        """Broadcast a message to all connections in a session."""
        if session_id not in self.active_connections:
            return

        # Convert message to JSON once
        json_message = json.dumps(message)

        # Send to all connected clients (copy set to avoid modification during iteration)
        disconnected = []
        for connection in list(self.active_connections[session_id]):
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


async def heartbeat_monitor(
    websocket: WebSocket,
    session_id: str,
    player_id: str,
    ping_interval: float = 30.0,
    pong_timeout: float = 5.0
) -> None:
    """
    Monitor connection health with ping/pong heartbeat.

    Sends ping messages at regular intervals and expects pong responses.
    Closes the connection if pong is not received within the timeout period.

    Args:
        websocket: WebSocket connection to monitor
        session_id: Game session ID
        player_id: Player identifier
        ping_interval: Seconds between pings (default: 30.0)
        pong_timeout: Seconds to wait for pong response (default: 5.0)
    """
    try:
        while session_id in _game_sessions:
            await asyncio.sleep(ping_interval)

            # Send ping
            try:
                await websocket.send_json({"type": "ping", "timestamp": time.time()})
            except Exception:
                # Failed to send ping - connection is dead
                logger.debug(f"Failed to send ping to player {player_id} - connection closed")
                break

            # Wait for pong
            await asyncio.sleep(pong_timeout)

            # Check if pong was received
            last_pong = manager.get_last_pong_time(websocket)
            time_since_pong = time.time() - last_pong

            if time_since_pong > (ping_interval + pong_timeout):
                # No recent pong - close connection
                logger.warning(
                    f"Player {player_id} failed to respond to ping "
                    f"(last pong: {time_since_pong:.1f}s ago) - closing connection"
                )
                try:
                    await websocket.close(code=1008, reason="Ping timeout")
                except Exception:
                    pass  # Connection might already be closed
                break

    except asyncio.CancelledError:
        # Task was cancelled (normal during disconnect)
        logger.debug(f"Heartbeat monitor for player {player_id} cancelled")
    except Exception as e:
        logger.error(f"Heartbeat monitor error for player {player_id}: {e}")


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

    # Start game loop if not already running
    if not engine._running:
        await engine.start_loop()

        # Start state broadcaster
        asyncio.create_task(state_broadcaster(session_id))

    # Start heartbeat monitor
    settings = get_settings()
    asyncio.create_task(
        heartbeat_monitor(
            websocket,
            session_id,
            player_id,
            ping_interval=settings.server.WEBSOCKET_PING_INTERVAL,
            pong_timeout=5.0
        )
    )

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
                    ],
                    'containment': {
                        'left_points': [list(p) for p in engine.state.track.containment.left_points],
                        'right_points': [list(p) for p in engine.state.track.containment.right_points]
                    } if engine.state.track.containment else None
                }
            }
        })

        # Add player to game AFTER successful connection message
        engine.add_player(player_id)

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

            elif message['type'] == 'pong':
                # Handle pong response - update last pong time
                manager.update_pong_time(websocket)

            elif message['type'] == 'start_race':
                # Start race countdown
                engine.start_race()

            elif message['type'] == 'submit_bot':
                # Submit a bot to the race
                bot_id = message['data'].get('bot_id')

                # Validate race status
                if engine.state.race_info.status not in [RaceStatus.WAITING, RaceStatus.RACING]:
                    await websocket.send_json({
                        'type': 'bot_submission_response',
                        'data': {'success': False, 'error': 'Invalid race status'}
                    })
                    continue

                # Fetch bot from database
                db = SessionLocal()
                try:
                    bot = bot_service.get_bot_by_id(db, bot_id)
                    if not bot:
                        await websocket.send_json({
                            'type': 'bot_submission_response',
                            'data': {'success': False, 'error': 'Bot not found'}
                        })
                        continue

                    # Extract class name
                    bot_class_name = bot_service.extract_class_name(bot.code)
                    if not bot_class_name:
                        await websocket.send_json({
                            'type': 'bot_submission_response',
                            'data': {'success': False, 'error': 'No bot class found'}
                        })
                        continue

                    # Create unique bot player ID
                    bot_player_id = f"bot-{bot.owner.username}-{bot.name}"

                    # Check if already in race
                    if bot_player_id in engine.state.players:
                        await websocket.send_json({
                            'type': 'bot_submission_response',
                            'data': {'success': False, 'error': 'Bot already in race'}
                        })
                        continue

                    # Add bot player
                    try:
                        engine.add_bot_player(bot_player_id, bot.code, bot_class_name)
                        await websocket.send_json({
                            'type': 'bot_submission_response',
                            'data': {
                                'success': True,
                                'bot_player_id': bot_player_id,
                                'bot_name': bot.name
                            }
                        })
                    except BotError as e:
                        await websocket.send_json({
                            'type': 'bot_submission_response',
                            'data': {'success': False, 'error': str(e)}
                        })
                finally:
                    db.close()

    except (WebSocketDisconnect, Exception) as e:
        # Player disconnected or connection error
        manager.disconnect(websocket, session_id)

        # Remove player from game engine
        try:
            engine.remove_player(player_id)
        except Exception:
            pass  # Player might not have been added yet

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
