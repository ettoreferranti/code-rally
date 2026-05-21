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
from app.core.lobby import LobbyStatus
from app.core.lobby_manager import get_lobby_manager
from app.config import get_settings
from app.database import SessionLocal
from app.services import bot_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/game", tags=["game"])

# Active game sessions (session_id -> GameEngine)
_game_sessions: Dict[str, GameEngine] = {}

# WebSocket connections (session_id -> set of WebSockets)
_connections: Dict[str, Set[WebSocket]] = {}

# Active state broadcasters (session_id set)
_active_broadcasters: Set[str] = set()

# Track which sessions came from lobbies (don't auto-cleanup on disconnect)
_lobby_sessions: Set[str] = set()

# Spectator connections (session_id -> set of WebSockets)
_spectator_connections: Dict[str, Set[WebSocket]] = {}


class ConnectionManager:
    """Manages WebSocket connections for multiplayer games."""

    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        # Track connection metadata (last pong time, player info)
        self.connection_metadata: Dict[WebSocket, dict] = {}
        # Track player ID to WebSocket mapping (for lobby messaging)
        self.player_to_ws: Dict[str, WebSocket] = {}

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

        # Track player -> websocket mapping
        self.player_to_ws[player_id] = websocket

    def disconnect(self, websocket: WebSocket, session_id: str) -> None:
        """Remove a WebSocket connection."""
        if session_id in self.active_connections:
            self.active_connections[session_id].discard(websocket)

            # Clean up empty sessions
            if not self.active_connections[session_id]:
                del self.active_connections[session_id]

        # Clean up metadata and player mapping
        if websocket in self.connection_metadata:
            player_id = self.connection_metadata[websocket].get('player_id')
            if player_id and player_id in self.player_to_ws:
                del self.player_to_ws[player_id]
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

    async def send_to_player(self, player_id: str, message: dict) -> bool:
        """
        Send a message to a specific player.

        Args:
            player_id: Player identifier
            message: Message to send

        Returns:
            True if sent successfully, False if player not connected
        """
        if player_id not in self.player_to_ws:
            return False

        websocket = self.player_to_ws[player_id]
        try:
            await websocket.send_json(message)
            return True
        except Exception:
            # Failed to send - connection might be dead
            return False


manager = ConnectionManager()


def _serialize_track(track) -> dict:
    """Serialize a Track into the JSON shape clients expect."""
    return {
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
            for seg in track.segments
        ],
        'checkpoints': [
            {
                'position': list(cp.position),
                'angle': cp.angle,
                'width': cp.width
            }
            for cp in track.checkpoints
        ],
        'start_position': list(track.start_position),
        'start_heading': track.start_heading,
        'obstacles': [
            {
                'position': list(obs.position),
                'radius': obs.radius,
                'type': obs.type
            }
            for obs in (track.obstacles or [])
        ],
        'containment': {
            'left_points': [list(p) for p in track.containment.left_points],
            'right_points': [list(p) for p in track.containment.right_points]
        } if track.containment else None
    }


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
    """Broadcast current game state to all players and spectators in a session."""
    if session_id not in _game_sessions:
        return

    engine = _game_sessions[session_id]
    state = engine.get_state_snapshot()

    # Inject spectator count
    spectator_count = len(_spectator_connections.get(session_id, set()))
    state['spectator_count'] = spectator_count

    message = {
        'type': 'game_state',
        'data': state
    }

    await manager.broadcast(message, session_id)

    # Also broadcast to spectators
    if session_id in _spectator_connections:
        json_message = json.dumps(message)
        disconnected = []
        for ws in list(_spectator_connections[session_id]):
            try:
                await ws.send_text(json_message)
            except Exception:
                disconnected.append(ws)
        for ws in disconnected:
            _spectator_connections[session_id].discard(ws)
            if not _spectator_connections[session_id]:
                del _spectator_connections[session_id]

    # When the engine race ends, propagate the FINISHED status back to
    # the lobby that owns this session. Without this, lobbies stay
    # listed as "in race" forever in the lobby browser.
    await _propagate_engine_finish_to_lobby(session_id)


async def _propagate_engine_finish_to_lobby(session_id: str) -> bool:
    """Flip the owning lobby RACING→FINISHED once the engine is FINISHED.

    Runs from two call sites:
      - ``broadcast_game_state`` — covers the common case where the host
        is still on the race screen when the race wraps up.
      - ``state_broadcaster`` — runs every tick regardless of whether any
        client is currently connected. This is the path that fixes the
        "stuck RACING" bug: when the host navigates away from /race
        before the race actually ends, the engine keeps ticking on the
        server and eventually transitions to FINISHED on its own. Without
        this second call site, the lobby was left pinned at RACING
        forever (visible in the lobby browser, un-resettable).

    Idempotent: ``finish_race`` returns True only on the first
    RACING→FINISHED transition, so subsequent calls are no-ops.
    Returns True iff the transition just fired (lobby flipped this call).
    """
    if session_id not in _lobby_sessions:
        return False
    engine = _game_sessions.get(session_id)
    if engine is None or engine.state.race_info.status != RaceStatus.FINISHED:
        return False
    lobby_manager = get_lobby_manager()
    lobby = lobby_manager.get_lobby_by_session(session_id)
    if lobby is None or not lobby_manager.finish_race(lobby.lobby_id):
        return False
    await broadcast_to_lobby(lobby.lobby_id, {
        'type': 'lobby_state',
        'data': serialize_lobby_state(lobby)
    })
    return True


async def state_broadcaster(session_id: str, update_rate: int = 60) -> None:
    """
    Background task to broadcast game state at regular intervals.

    Args:
        session_id: Game session to broadcast
        update_rate: Updates per second (Hz)
    """
    global _active_broadcasters

    # Mark this broadcaster as active
    _active_broadcasters.add(session_id)

    try:
        interval = 1.0 / update_rate

        while session_id in _game_sessions:
            if session_id in manager.active_connections:
                await broadcast_game_state(session_id)
            else:
                # No active connections — still need to flip the lobby
                # to FINISHED when the engine finishes on its own. The
                # heavy state_snapshot work in broadcast_game_state is
                # skipped (no one to send it to).
                await _propagate_engine_finish_to_lobby(session_id)
            await asyncio.sleep(interval)
    finally:
        # Clean up when broadcaster stops
        _active_broadcasters.discard(session_id)


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


# ===== Lobby Functions =====

async def broadcast_to_lobby(lobby_id: str, message: dict, exclude_player_id: Optional[str] = None) -> None:
    """
    Broadcast a message to all members and spectators of a lobby.

    Args:
        lobby_id: Lobby identifier
        message: Message to broadcast
        exclude_player_id: Optional player ID to exclude from broadcast
    """
    lobby_manager = get_lobby_manager()
    lobby = lobby_manager.get_lobby(lobby_id)

    if not lobby:
        return

    # Send to all members
    for member in lobby.members.values():
        if exclude_player_id and member.player_id == exclude_player_id:
            continue

        await manager.send_to_player(member.player_id, message)

    # Send to all spectators
    for spectator in lobby.spectators.values():
        if exclude_player_id and spectator.player_id == exclude_player_id:
            continue

        await manager.send_to_player(spectator.player_id, message)


def serialize_lobby_state(lobby) -> dict:
    """
    Serialize lobby state for WebSocket transmission.

    Args:
        lobby: Lobby dataclass

    Returns:
        Serialized lobby state
    """
    return {
        'lobby_id': lobby.lobby_id,
        'join_code': lobby.join_code,
        'name': lobby.name,
        'host_player_id': lobby.host_player_id,
        'creator_player_id': lobby.creator_player_id,
        'status': lobby.status.value,
        'settings': {
            'track_difficulty': lobby.settings.track_difficulty,
            'track_length': lobby.settings.track_length,
            'track_curves': lobby.settings.track_curves,
            'track_seed': lobby.settings.track_seed,
            'max_players': lobby.settings.max_players,
            'finish_grace_period': lobby.settings.finish_grace_period
        },
        'members': [
            {
                'player_id': member.player_id,
                'username': member.username,
                'driver_kind': member.driver_kind,
                'is_bot': member.is_bot,
                'bot_id': member.bot_id,
                'ready': member.ready,
                'llm_model_path': member.llm_model_path,
                # llm_system_prompt deliberately omitted from the payload —
                # it can be long and the roster doesn't need it. Frontend
                # can fetch the bot row from /bots/{id} if needed.
            }
            for member in lobby.members.values()
        ],
        'game_session_id': lobby.game_session_id,
        'spectator_count': lobby.get_spectator_count()
    }


async def handle_join_lobby(lobby_id: str, player_id: str, username: Optional[str], websocket: WebSocket) -> None:
    """
    Handle player joining a lobby via WebSocket.

    Args:
        lobby_id: Lobby to join
        player_id: Player identifier
        username: Optional player username
        websocket: WebSocket connection
    """
    lobby_manager = get_lobby_manager()

    # Join lobby
    success = lobby_manager.join_lobby(lobby_id, player_id, username)

    if not success:
        await websocket.send_json({
            'type': 'error',
            'data': {'message': 'Failed to join lobby (not found, full, or wrong status)'}
        })
        return

    # Get updated lobby
    lobby = lobby_manager.get_lobby(lobby_id)

    # Send lobby joined confirmation with player_id to joining player
    await websocket.send_json({
        'type': 'lobby_joined',
        'data': {
            'player_id': player_id,
            'lobby': serialize_lobby_state(lobby)
        }
    })

    # Broadcast updated lobby state to OTHER members (exclude self)
    await broadcast_to_lobby(lobby_id, {
        'type': 'lobby_state',
        'data': serialize_lobby_state(lobby)
    }, exclude_player_id=player_id)


async def handle_leave_lobby(lobby_id: str, player_id: str) -> None:
    """
    Handle player leaving a lobby.

    Fired from two places:
      - Explicit "leave_lobby" message (user hit the leave button), AND
      - Lobby WebSocket disconnect (browser closed, network drop, OR the
        frontend navigated from /lobby/:id to /race?session=...).

    The third case is the gotcha: when a race starts, the lobby
    transitions to RACING and broadcasts the change. The frontend then
    swaps routes from /lobby to /race, which CLOSES the lobby WS — which
    looks identical to "user left" from the backend's POV. Without the
    guard below we'd then call ``leave_lobby``, remove the player from
    membership, and trigger a host transfer ("transferred from X to X"
    when X reconnects under the same player_id on the race WS).

    Skip the leave when the lobby is in RACING/STARTING — the player
    is in the race, not gone. Their membership stays so they re-enter
    the lobby cleanly when the race ends.

    Args:
        lobby_id: Lobby to leave
        player_id: Player identifier
    """
    lobby_manager = get_lobby_manager()
    lobby = lobby_manager.get_lobby(lobby_id)

    if lobby is not None and lobby.status in (LobbyStatus.STARTING, LobbyStatus.RACING):
        logger.info(
            f"Player {player_id} disconnected from lobby {lobby_id} while "
            f"in {lobby.status.value} — treating as in-race (membership preserved)"
        )
        return

    # Leave lobby (also handles host transfer and auto-disband)
    lobby_manager.leave_lobby(lobby_id, player_id)

    # Broadcast member left
    await broadcast_to_lobby(lobby_id, {
        'type': 'lobby_member_left',
        'data': {'player_id': player_id}
    })

    # Note: If lobby was disbanded, broadcast_to_lobby will do nothing (lobby gone)


async def handle_lobby_start_race(lobby_id: str, player_id: str, websocket: WebSocket) -> None:
    """
    Handle host starting race from lobby.

    Args:
        lobby_id: Lobby identifier
        player_id: Player attempting start (must be host)
        websocket: WebSocket connection
    """
    lobby_manager = get_lobby_manager()

    # Start race (validates host, creates track, transitions to STARTING)
    result = lobby_manager.start_race(lobby_id, player_id)

    if not result:
        await websocket.send_json({
            'type': 'error',
            'data': {'message': 'Failed to start race (not host, wrong status, or lobby not found)'}
        })
        return

    game_session_id, track = result

    # Create game engine
    engine = GameEngine(track)
    _game_sessions[game_session_id] = engine

    # Mark this session as coming from a lobby (don't auto-cleanup on player disconnect)
    _lobby_sessions.add(game_session_id)

    # Add all lobby members to game engine, dispatching by driver_kind.
    lobby = lobby_manager.get_lobby(lobby_id)
    for member in lobby.members.values():
        if member.driver_kind == "llm_bot":
            try:
                # Pass the bot's stored system_prompt through to the
                # strategist so every LLM bot races with its own
                # personality (or the default if none was customised).
                strategist_kwargs = {}
                if member.llm_system_prompt is not None:
                    strategist_kwargs["system_prompt"] = member.llm_system_prompt
                engine.add_llm_player(
                    member.player_id,
                    model_path=member.llm_model_path,
                    strategist_kwargs=strategist_kwargs or None,
                    bot_name=member.bot_name,
                )
            except BotError as e:
                logger.error(f"Failed to add LLM bot {member.player_id} to race: {e}")
                await websocket.send_json({
                    'type': 'error',
                    'data': {'message': f'LLM bot failed to load: {e}'}
                })
        elif member.driver_kind == "python_bot" or member.is_bot:
            try:
                engine.add_bot_player(
                    member.player_id,
                    member.bot_code,
                    member.bot_class_name,
                    bot_name=member.bot_name,
                )
            except BotError as e:
                logger.error(f"Failed to add bot {member.player_id} to race: {e}")
        else:
            engine.add_player(member.player_id)

    # Start engine loop, then spawn any LLM strategist tasks bound to the race.
    await engine.start_loop()
    await engine.start_agents()

    # Don't start broadcaster here - it will be started when first player connects
    # (prevents broadcaster from exiting immediately due to no connections)

    # Transition lobby to RACING
    lobby_manager.transition_to_racing(lobby_id)

    # Broadcast race starting to all lobby members
    await broadcast_to_lobby(lobby_id, {
        'type': 'race_starting',
        'data': {
            'game_session_id': game_session_id,
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
                    for seg in track.segments
                ],
                'checkpoints': [
                    {
                        'position': list(cp.position),
                        'angle': cp.angle,
                        'width': cp.width
                    }
                    for cp in track.checkpoints
                ],
                'start_position': list(track.start_position),
                'start_heading': track.start_heading,
                'obstacles': [
                    {
                        'position': list(obs.position),
                        'radius': obs.radius,
                        'type': obs.type
                    }
                    for obs in (track.obstacles or [])
                ],
                'containment': {
                    'left_points': [list(p) for p in track.containment.left_points],
                    'right_points': [list(p) for p in track.containment.right_points]
                } if track.containment else None
            }
        }
    })

    # Any spectators that were already in the lobby (status=WAITING ⇒
    # status=RACING transition just happened) need to start receiving
    # game-state broadcasts. Their websockets live in
    # ``manager.active_connections[lobby_id]``; we look up each one
    # via the player_id → WS map and register it for the session's
    # spectator pool. (Spectators joining AFTER the race already
    # started are handled in the lobby-spectate WS branch.)
    if lobby.spectators:
        for spectator_player_id in list(lobby.spectators.keys()):
            ws = manager.player_to_ws.get(spectator_player_id)
            if ws is None:
                continue  # spectator's WS already closed
            if game_session_id not in _spectator_connections:
                _spectator_connections[game_session_id] = set()
            _spectator_connections[game_session_id].add(ws)


async def handle_add_bot_to_lobby(lobby_id: str, player_id: str, bot_id: int, websocket: WebSocket) -> None:
    """
    Add a bot (Python or LLM) from the user's library to a lobby.

    Reads the bot row from the DB, dispatches by ``bot.kind`` into the
    unified ``LobbyManager.add_bot_to_lobby``. Surfaces MLX-missing and
    other kind-specific errors with helpful messages.
    """
    lobby_manager = get_lobby_manager()

    db = SessionLocal()
    try:
        bot = bot_service.get_bot_by_id(db, bot_id)
        if not bot:
            await websocket.send_json({
                'type': 'error',
                'data': {'message': 'Bot not found'}
            })
            return

        owner_username = bot.owner.username

        if bot.kind == "python_bot" or bot.kind == "python":
            bot_class_name = bot_service.extract_class_name(bot.code)
            if not bot_class_name:
                await websocket.send_json({
                    'type': 'error',
                    'data': {'message': 'No bot class found in code'}
                })
                return
            lobby_player_id = lobby_manager.add_bot_to_lobby(
                lobby_id=lobby_id,
                bot_id=bot_id,
                kind="python_bot",
                bot_name=bot.name,
                owner_username=owner_username,
                bot_code=bot.code,
                bot_class_name=bot_class_name,
            )
        elif bot.kind == "llm" or bot.kind == "llm_bot":
            lobby_player_id = lobby_manager.add_bot_to_lobby(
                lobby_id=lobby_id,
                bot_id=bot_id,
                kind="llm_bot",
                bot_name=bot.name,
                owner_username=owner_username,
                model_path=bot.model_path,
                system_prompt=bot.system_prompt,
            )
        else:
            await websocket.send_json({
                'type': 'error',
                'data': {'message': f'Unknown bot kind: {bot.kind!r}'}
            })
            return

        if not lobby_player_id:
            # Distinguish MLX-missing for the host-facing error.
            if bot.kind in ("llm", "llm_bot"):
                from app.agents import mlx_runtime
                if not mlx_runtime.is_available():
                    message = (
                        'MLX is not installed on the server. Install '
                        'backend/requirements-agents.txt to enable LLM bots '
                        '(Apple Silicon only).'
                    )
                else:
                    message = 'Failed to add LLM bot (lobby full, wrong status, or already added)'
            else:
                message = 'Failed to add bot (lobby full, wrong status, or already added)'
            await websocket.send_json({
                'type': 'error',
                'data': {'message': message}
            })
            return

        lobby = lobby_manager.get_lobby(lobby_id)
        await broadcast_to_lobby(lobby_id, {
            'type': 'lobby_state',
            'data': serialize_lobby_state(lobby)
        })

    finally:
        db.close()


async def handle_spectate_lobby(lobby_id: str, player_id: str, username: Optional[str], websocket: WebSocket) -> None:
    """
    Handle spectator joining a lobby via WebSocket.

    Args:
        lobby_id: Lobby to spectate
        player_id: Spectator identifier
        username: Optional spectator username
        websocket: WebSocket connection
    """
    lobby_manager = get_lobby_manager()

    # Join as spectator
    success = lobby_manager.spectate_lobby(lobby_id, player_id, username)

    if not success:
        await websocket.send_json({
            'type': 'error',
            'data': {'message': 'Failed to spectate lobby (not found or wrong status)'}
        })
        return

    # Get lobby state
    lobby = lobby_manager.get_lobby(lobby_id)

    # Send spectator joined confirmation
    await websocket.send_json({
        'type': 'spectator_joined',
        'data': {
            'player_id': player_id,
            'lobby': serialize_lobby_state(lobby)
        }
    })

    # Broadcast updated lobby state to other members and spectators
    await broadcast_to_lobby(lobby_id, {
        'type': 'lobby_state',
        'data': serialize_lobby_state(lobby)
    }, exclude_player_id=player_id)


async def handle_leave_spectate(lobby_id: str, player_id: str) -> None:
    """
    Handle spectator leaving a lobby.

    Args:
        lobby_id: Lobby to leave
        player_id: Spectator identifier
    """
    lobby_manager = get_lobby_manager()
    lobby_manager.remove_spectator(lobby_id, player_id)

    # Broadcast updated state
    lobby = lobby_manager.get_lobby(lobby_id)
    if lobby:
        await broadcast_to_lobby(lobby_id, {
            'type': 'lobby_state',
            'data': serialize_lobby_state(lobby)
        })


@router.websocket("/ws")
async def game_websocket(
    websocket: WebSocket,
    lobby_id: Optional[str] = Query(default=None),
    session_id: Optional[str] = Query(default=None),
    player_id: Optional[str] = Query(default=None),
    difficulty: str = Query(default="medium"),
    seed: Optional[int] = Query(default=None),
    spectate: bool = Query(default=False)
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
    # Use provided player ID (username) or generate unique ID
    if not player_id:
        player_id = str(uuid4())

    # Determine connection mode
    is_lobby_mode = lobby_id is not None
    is_spectator = spectate

    if is_lobby_mode:
        # Connect to lobby WebSocket
        await manager.connect(websocket, lobby_id, player_id)

        if is_spectator:
            # Spectator mode - join as spectator
            await handle_spectate_lobby(lobby_id, player_id, player_id, websocket)

            # If lobby is already racing, send track data and connect to game session
            lobby_manager = get_lobby_manager()
            lobby = lobby_manager.get_lobby(lobby_id)
            if lobby and lobby.status == LobbyStatus.RACING and lobby.game_session_id:
                game_sid = lobby.game_session_id
                if game_sid in _game_sessions:
                    engine_for_track = _game_sessions[game_sid]
                    track = engine_for_track.state.track
                    await websocket.send_json({
                        'type': 'race_starting',
                        'data': {
                            'game_session_id': game_sid,
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
                                    for seg in track.segments
                                ],
                                'checkpoints': [
                                    {
                                        'position': list(cp.position),
                                        'angle': cp.angle,
                                        'width': cp.width
                                    }
                                    for cp in track.checkpoints
                                ],
                                'start_position': list(track.start_position),
                                'start_heading': track.start_heading,
                                'obstacles': [
                                    {
                                        'position': list(obs.position),
                                        'radius': obs.radius,
                                        'type': obs.type
                                    }
                                    for obs in (track.obstacles or [])
                                ],
                                'containment': {
                                    'left_points': [list(p) for p in track.containment.left_points],
                                    'right_points': [list(p) for p in track.containment.right_points]
                                } if track.containment else None
                            }
                        }
                    })
                    # Register this websocket for the game-state broadcast.
                    # Without this, ``broadcast_game_state`` only ships to
                    # ``manager.active_connections[session_id]`` and the
                    # session's spectator pool — neither of which contains
                    # a lobby-mode spectator, whose WS lives in
                    # ``active_connections[lobby_id]``. Result before the
                    # fix: the spectator sat on a "Waiting for game
                    # state..." screen indefinitely.
                    if game_sid not in _spectator_connections:
                        _spectator_connections[game_sid] = set()
                    _spectator_connections[game_sid].add(websocket)
        else:
            # Regular player mode - join lobby as member
            await handle_join_lobby(lobby_id, player_id, player_id, websocket)

        # Note: Session will be created when host starts race
        session_id = None
        engine = None
    elif is_spectator and session_id:
        # Direct spectate mode - spectate an existing game session
        await websocket.accept()

        # Add to spectator connections
        if session_id not in _spectator_connections:
            _spectator_connections[session_id] = set()
        _spectator_connections[session_id].add(websocket)

        # Send connected message with track data
        if session_id in _game_sessions:
            engine = _game_sessions[session_id]
            track = engine.state.track
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
                            for seg in track.segments
                        ],
                        'checkpoints': [
                            {
                                'position': list(cp.position),
                                'angle': cp.angle,
                                'width': cp.width
                            }
                            for cp in track.checkpoints
                        ],
                        'start_position': list(track.start_position),
                        'start_heading': track.start_heading,
                        'obstacles': [
                            {
                                'position': list(obs.position),
                                'radius': obs.radius,
                                'type': obs.type
                            }
                            for obs in (track.obstacles or [])
                        ],
                        'containment': {
                            'left_points': [list(p) for p in track.containment.left_points],
                            'right_points': [list(p) for p in track.containment.right_points]
                        } if track.containment else None
                    }
                }
            })

        engine = None  # Spectators don't have engine access
    else:
        # Direct mode (legacy) - create/join session immediately
        session_id, engine = get_or_create_session(session_id, difficulty, seed)

        # Connect player
        await manager.connect(websocket, session_id, player_id)

    # Start game loop and send initial messages (direct mode only, not spectators)
    if not is_lobby_mode and not is_spectator:
        if not engine._running:
            await engine.start_loop()

        # Start state broadcaster if not already running
        if session_id not in _active_broadcasters:
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

        # Send initial connection success message (direct mode only)
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
        # Only add if not already in engine (e.g., from lobby)
        if player_id not in engine.state.players:
            engine.add_player(player_id)

    try:
        # Listen for player inputs and lobby messages
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            message = json.loads(data)

            # Spectators can only send pong and leave messages
            if is_spectator:
                if message['type'] == 'pong':
                    manager.update_pong_time(websocket)
                elif message['type'] == 'leave_lobby' and is_lobby_mode:
                    await handle_leave_spectate(lobby_id, player_id)
                    break
                # All other messages (input, start_race, etc.) are silently ignored
                continue

            # Lobby-specific messages
            if message['type'] == 'leave_lobby':
                await handle_leave_lobby(lobby_id, player_id)
                break  # Exit loop after leaving

            elif message['type'] == 'start_race' and is_lobby_mode:
                # Host starting race from lobby
                await handle_lobby_start_race(lobby_id, player_id, websocket)

            elif message['type'] == 'add_bot_to_lobby':
                # Unified add-bot: backend reads bot.kind from DB and dispatches.
                bot_id = (message.get('data') or {}).get('bot_id')
                await handle_add_bot_to_lobby(lobby_id, player_id, bot_id, websocket)

            # Game input messages
            elif message['type'] == 'input':
                # Update player input (only if engine exists)
                if engine:
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

            elif message['type'] == 'start_race' and not is_lobby_mode:
                # Start race countdown (direct mode only)
                if engine:
                    engine.start_race()

            elif message['type'] == 'regenerate_track':
                # Reroll the track for the current session/lobby. Refused
                # while the race is actively running; everyone connected
                # receives the new track and is reset to the new start line.
                target_engine = engine
                if target_engine is None and is_lobby_mode:
                    lobby = get_lobby_manager().get_lobby(lobby_id)
                    if lobby and lobby.game_session_id in _game_sessions:
                        target_engine = _game_sessions[lobby.game_session_id]

                if target_engine is None:
                    await websocket.send_json({
                        'type': 'error',
                        'data': {'message': 'No active race session to regenerate'}
                    })
                elif target_engine.state.race_info.status == RaceStatus.RACING:
                    await websocket.send_json({
                        'type': 'error',
                        'data': {'message': 'Cannot change track while race is running'}
                    })
                else:
                    raw_seed = (message.get('data') or {}).get('seed')
                    try:
                        new_seed = int(raw_seed) if raw_seed is not None else None
                    except (TypeError, ValueError):
                        new_seed = None

                    # Honor lobby track-shape settings if this engine
                    # belongs to a lobby; otherwise fall back to defaults.
                    gen_kwargs = {'difficulty': 'medium', 'length': 'medium', 'curves': 'mixed'}
                    if is_lobby_mode:
                        lobby = get_lobby_manager().get_lobby(lobby_id)
                        if lobby:
                            gen_kwargs['difficulty'] = lobby.settings.track_difficulty
                            gen_kwargs['length'] = lobby.settings.track_length
                            gen_kwargs['curves'] = lobby.settings.track_curves

                    new_track = TrackGenerator(seed=new_seed).generate(**gen_kwargs)
                    target_engine.reset_to_new_track(new_track)

                    payload = {
                        'type': 'track_changed',
                        'data': {'track': _serialize_track(new_track)}
                    }
                    if is_lobby_mode:
                        await broadcast_to_lobby(lobby_id, payload)
                    else:
                        await manager.broadcast(payload, session_id)

            # Mid-race `submit_bot` was removed in the Tinker / unified
            # lobby cleanup. All bots are now added pre-race via
            # `add_bot_to_lobby` while the lobby is still WAITING.

    except (WebSocketDisconnect, Exception) as e:
        # Handle disconnect cleanup
        if is_spectator:
            # Spectator disconnect
            if is_lobby_mode:
                manager.disconnect(websocket, lobby_id)
                await handle_leave_spectate(lobby_id, player_id)
                # If we registered this lobby-spectator's WS for the
                # session's game-state broadcast (RACING lobby), drop
                # it from there too — otherwise the next broadcast
                # would try to send to a closed socket.
                lobby_for_session = get_lobby_manager().get_lobby(lobby_id)
                game_sid = lobby_for_session.game_session_id if lobby_for_session else None
                if game_sid and game_sid in _spectator_connections:
                    _spectator_connections[game_sid].discard(websocket)
                    if not _spectator_connections[game_sid]:
                        del _spectator_connections[game_sid]
            else:
                # Direct spectate - remove from spectator connections
                if session_id in _spectator_connections:
                    _spectator_connections[session_id].discard(websocket)
                    if not _spectator_connections[session_id]:
                        del _spectator_connections[session_id]
        elif is_lobby_mode:
            # Lobby mode - handle leave and cleanup
            manager.disconnect(websocket, lobby_id)
            await handle_leave_lobby(lobby_id, player_id)
        else:
            # Direct mode - cleanup session
            manager.disconnect(websocket, session_id)

            # Remove player from game engine (only for non-lobby sessions)
            # Lobby sessions manage their own player lifecycle
            if engine and session_id not in _lobby_sessions:
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
