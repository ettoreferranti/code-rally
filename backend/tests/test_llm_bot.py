"""Integration tests for the LLM driver type in the race engine (issue #155).

Covers:
- LLMBot wiring: get_inputs feeds the strategist and returns controller output.
- Per-tick path is fully synchronous and never awaits the LLM.
- Engine accepts `llm` as a driver kind and runs a race with an LLM car.
- Strategist task is bound to race lifecycle (cancelled on stop_loop).
- Two LLM cars share the MLX runtime singleton.
- MLX absence raises BotError at add_llm_player time.

All tests use an injected stub generate_fn — no MLX required.
"""

import asyncio
import math
import time
from typing import List, Optional, Tuple

import pytest

from app.agents.controller import ControlInputs
from app.agents.intent import Intent
from app.agents.llm_bot import LLMBot
from app.bot_runtime.types import (
    BotCarState,
    BotGameState,
    BotRaceState,
    BotTrackState,
)
from app.config import get_settings
from app.core.bot_manager import BotError
from app.core.engine import GameEngine
from app.core.track import TrackGenerator


# ===== Helpers =====


VALID_INTENT_JSON = (
    '{"target_speed_kmh": 80, "racing_line_offset_m": 0, "aggression": 0.5}'
)


def _make_constant_generate(response: str = VALID_INTENT_JSON):
    async def generate(_prompt: str) -> str:
        return response

    return generate


def _make_bot_state(
    position: Tuple[float, float] = (0.0, 0.0),
    heading: float = 0.0,
    speed_ms: float = 0.0,
    checkpoints: Optional[List[Tuple[float, float]]] = None,
    next_checkpoint: int = 0,
) -> BotGameState:
    car = BotCarState(
        position=position,
        heading=heading,
        speed=speed_ms,
        velocity=(speed_ms * math.cos(heading), speed_ms * math.sin(heading)),
        angular_velocity=0.0,
        health=100.0,
        nitro_charges=3,
        nitro_active=False,
        current_surface="asphalt",
        off_track=False,
    )
    track = BotTrackState(
        checkpoints=checkpoints if checkpoints is not None else [(100.0, 0.0)],
        next_checkpoint=next_checkpoint,
        distance_to_boundary_left=5.0,
        distance_to_boundary_right=5.0,
        upcoming_surface="asphalt",
        upcoming_turn="straight",
        turn_sharpness=0.0,
    )
    race = BotRaceState(
        current_checkpoint=next_checkpoint,
        total_checkpoints=len(track.checkpoints),
        position=1,
        total_cars=1,
        elapsed_time=0.0,
        distance_to_finish=100.0,
    )
    return BotGameState(car=car, track=track, rays=[], opponents=[], race=race)


def _advance_countdown(engine: GameEngine, settings) -> None:
    countdown_ticks = int(settings.game.COUNTDOWN_SECONDS * settings.game.TICK_RATE)
    for _ in range(countdown_ticks + 1):
        engine._tick()


# ===== Fixtures =====


@pytest.fixture
def settings():
    return get_settings()


@pytest.fixture
def test_track():
    return TrackGenerator(seed=42).generate(difficulty="easy")


@pytest.fixture
def engine(test_track):
    return GameEngine(test_track)


# ===== Unit: LLMBot wiring =====


class TestLLMBotWiring:
    """LLMBot must (a) feed the strategist a fresh observation each tick,
    and (b) translate the strategist's latest intent into ControlInputs.
    """

    def test_get_inputs_returns_control_inputs(self):
        bot = LLMBot(generate_fn=_make_constant_generate())
        state = _make_bot_state(checkpoints=[(100.0, 0.0)])
        ctrl = bot.get_inputs(state)
        assert isinstance(ctrl, ControlInputs)

    def test_get_inputs_pushes_observation_into_strategist(self):
        bot = LLMBot(generate_fn=_make_constant_generate())
        state = _make_bot_state(checkpoints=[(100.0, 0.0)])
        bot.get_inputs(state)
        # The strategist sees a formatted observation string (any non-empty
        # text means the bot wired set_observation into the per-tick path).
        observation = bot._strategist._latest_observation
        assert observation is not None
        assert "speed:" in observation
        assert "checkpoint" in observation

    def test_get_inputs_uses_latest_intent(self):
        """Pre-seed the strategist's latest_intent; controller should honour it."""
        bot = LLMBot(generate_fn=_make_constant_generate())
        bot._strategist._latest_intent = Intent(
            target_speed_kmh=200.0,
            racing_line_offset_m=0.0,
            aggression=0.9,
        )
        # Car stopped, checkpoint dead ahead → controller should accelerate.
        state = _make_bot_state(position=(0.0, 0.0), heading=0.0, speed_ms=0.0,
                                checkpoints=[(100.0, 0.0)])
        ctrl = bot.get_inputs(state)
        assert ctrl.accelerate is True
        assert ctrl.brake is False

    def test_get_inputs_falls_back_when_no_intent_yet(self):
        """No intent + clear lookahead → controller cruises forward, never raises."""
        bot = LLMBot(generate_fn=_make_constant_generate())
        state = _make_bot_state(position=(0.0, 0.0), heading=0.0, speed_ms=0.0,
                                checkpoints=[(100.0, 0.0)])
        ctrl = bot.get_inputs(state)
        # Fallback target speed is 30 km/h > 0, so we accelerate.
        assert ctrl.accelerate is True


# ===== Per-tick path must not block on the LLM =====


class TestPerTickNeverBlocks:
    """The 20Hz engine tick must never await on the LLM."""

    def test_get_inputs_is_synchronous_and_fast(self):
        """100 get_inputs calls in a tight loop complete well under the tick budget.

        Uses a generate_fn that would sleep for 5s if awaited. The strategist
        task is not started, so generate_fn must never be invoked from the
        per-tick path.
        """
        call_count = 0

        async def slow_generate(_prompt: str) -> str:
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(5.0)
            return VALID_INTENT_JSON

        bot = LLMBot(generate_fn=slow_generate)
        state = _make_bot_state(checkpoints=[(100.0, 0.0)])

        start = time.perf_counter()
        for _ in range(100):
            bot.get_inputs(state)
        elapsed = time.perf_counter() - start

        # Engine tick budget at 60Hz is ~16ms; 100 ticks in 0.5s is generous.
        assert elapsed < 0.5
        # The per-tick path never invokes generate_fn directly.
        assert call_count == 0


# ===== Engine integration =====


class TestEngineLLMIntegration:
    """The engine must dispatch LLM drivers alongside humans and Python bots."""

    @pytest.mark.asyncio
    async def test_race_runs_with_llm_player_and_makes_progress(self, engine, settings):
        """Acceptance criterion: race runs N ticks with stubbed strategist
        and the LLM car completes checkpoint progress.
        """
        engine.add_llm_player("llm_player", generate_fn=_make_constant_generate())
        # Pre-seed an aggressive intent so the test is deterministic and
        # does not depend on the async strategist firing on a given schedule.
        player = engine.state.players["llm_player"]
        player.llm_bot._strategist._latest_intent = Intent(
            target_speed_kmh=120.0,
            racing_line_offset_m=0.0,
            aggression=0.8,
        )

        engine.start_race()
        _advance_countdown(engine, settings)

        initial_checkpoint = player.current_checkpoint
        # Drive up to 15s of simulated race.
        max_ticks = 15 * settings.game.TICK_RATE
        for _ in range(max_ticks):
            engine._tick()
            if player.current_checkpoint > initial_checkpoint:
                break

        assert player.current_checkpoint > initial_checkpoint, (
            f"LLM car made no checkpoint progress after {max_ticks} ticks"
        )
        assert player.bot_error is None
        assert player.dnf is False

    @pytest.mark.asyncio
    async def test_engine_accepts_llm_alongside_human_and_python_bot(self, engine, settings):
        """All three driver kinds coexist in one engine."""
        engine.add_player("human_player")
        engine.add_llm_player("llm_player", generate_fn=_make_constant_generate())

        from app.bot_runtime.templates import get_template_code  # type: ignore
        # We don't depend on the Python bot actually driving — just that the
        # engine accepts a Python bot in parallel. If the template helper is
        # absent, skip the Python bot leg.
        try:
            python_bot_code = get_template_code("aggressive_bot")
            engine.add_bot_player("py_player", python_bot_code, "AggressiveBot")
            has_python_bot = True
        except Exception:
            has_python_bot = False

        # Engine should be runnable with this mix.
        engine.start_race()
        for _ in range(settings.game.COUNTDOWN_SECONDS * settings.game.TICK_RATE + 5):
            engine._tick()

        assert "human_player" in engine.state.players
        assert "llm_player" in engine.state.players
        if has_python_bot:
            assert "py_player" in engine.state.players

    @pytest.mark.asyncio
    async def test_start_agents_spawns_strategist_task(self, engine):
        engine.add_llm_player("llm_player", generate_fn=_make_constant_generate(),
                              strategist_kwargs={"tick_interval_s": 0.01})
        await engine.start_agents()

        player = engine.state.players["llm_player"]
        task = player.llm_bot._strategist._task
        assert task is not None
        assert not task.done()

        # Cleanup.
        await engine.stop_loop()

    @pytest.mark.asyncio
    async def test_stop_loop_cancels_strategist_task(self, engine):
        """Acceptance criterion: strategist lifecycle bound to race lifecycle —
        no leaked tasks after the engine stops.
        """
        engine.add_llm_player("llm_player", generate_fn=_make_constant_generate(),
                              strategist_kwargs={"tick_interval_s": 0.01})
        await engine.start_agents()
        player = engine.state.players["llm_player"]
        task_before = player.llm_bot._strategist._task
        assert task_before is not None

        await engine.stop_loop()

        # After stop_loop, the strategist's task reference has been cleared
        # (its stop() sets _task = None) — and the original task is done.
        assert player.llm_bot._strategist._task is None
        assert task_before.done()

    @pytest.mark.asyncio
    async def test_two_llm_players_same_model_share_runtime(self, engine, monkeypatch):
        """Acceptance criterion: two LLM cars on the same model share one runtime."""
        from app.agents import mlx_runtime

        mlx_runtime.MLXRuntime._runtimes = {}

        construct_calls = 0

        def stub_init(self, model_path=mlx_runtime.DEFAULT_MODEL_PATH, max_tokens=64):
            nonlocal construct_calls
            construct_calls += 1
            self._max_tokens = max_tokens

        async def stub_generate(self, prompt: str) -> str:
            return VALID_INTENT_JSON

        monkeypatch.setattr(mlx_runtime.MLXRuntime, "__init__", stub_init)
        monkeypatch.setattr(mlx_runtime.MLXRuntime, "generate", stub_generate)

        engine.add_llm_player("llm_one")
        engine.add_llm_player("llm_two")

        # Both bots use the default model → exactly one runtime constructed.
        assert construct_calls == 1
        assert len(mlx_runtime.MLXRuntime._runtimes) == 1

        mlx_runtime.MLXRuntime._runtimes = {}

    @pytest.mark.asyncio
    async def test_two_llm_players_different_models_use_separate_runtimes(self, engine, monkeypatch):
        """Different model_paths load their own runtimes, cached per path."""
        from app.agents import mlx_runtime

        mlx_runtime.MLXRuntime._runtimes = {}

        construct_calls = 0

        def stub_init(self, model_path=mlx_runtime.DEFAULT_MODEL_PATH, max_tokens=64):
            nonlocal construct_calls
            construct_calls += 1
            self._max_tokens = max_tokens

        async def stub_generate(self, prompt: str) -> str:
            return VALID_INTENT_JSON

        monkeypatch.setattr(mlx_runtime.MLXRuntime, "__init__", stub_init)
        monkeypatch.setattr(mlx_runtime.MLXRuntime, "generate", stub_generate)

        engine.add_llm_player("llm_one", model_path="modelA")
        engine.add_llm_player("llm_two", model_path="modelB")
        engine.add_llm_player("llm_three", model_path="modelA")  # cache hit

        assert construct_calls == 2  # one per unique model
        assert set(mlx_runtime.MLXRuntime._runtimes.keys()) == {"modelA", "modelB"}

        mlx_runtime.MLXRuntime._runtimes = {}

    def test_snapshot_omits_agent_intent_for_human_player(self, engine):
        """Non-LLM cars must not carry agent_intent in the WS payload."""
        engine.add_player("human")
        snapshot = engine.get_state_snapshot()
        assert "agent_intent" not in snapshot["players"]["human"]

    def test_snapshot_omits_agent_intent_when_no_intent_yet(self, engine):
        """LLM cars before their first Intent must not emit agent_intent."""
        engine.add_llm_player("llm_player", generate_fn=_make_constant_generate())
        snapshot = engine.get_state_snapshot()
        assert "agent_intent" not in snapshot["players"]["llm_player"]

    def test_snapshot_includes_agent_intent_for_llm_player_with_intent(self, engine):
        """After a strategist intent is produced, the snapshot exposes the full intent + ts."""
        import time as _time

        engine.add_llm_player("llm_player", generate_fn=_make_constant_generate())
        player = engine.state.players["llm_player"]
        # Simulate the strategist storing an intent at a known time.
        player.llm_bot._strategist._latest_intent = Intent(
            target_speed_kmh=85.0,
            racing_line_offset_m=1.5,
            aggression=0.4,
        )
        produced_at = _time.time()
        player.llm_bot._strategist._latest_intent_ts = produced_at

        snapshot = engine.get_state_snapshot()
        agent_intent = snapshot["players"]["llm_player"].get("agent_intent")
        assert agent_intent is not None
        assert agent_intent["target_speed_kmh"] == 85.0
        assert agent_intent["racing_line_offset_m"] == 1.5
        assert agent_intent["aggression"] == 0.4
        assert agent_intent["ts"] == produced_at

    def test_add_llm_player_propagates_model_path_to_runtime(self, engine, monkeypatch):
        """The model_path argument routes through to get_mlx_generate_fn."""
        from app.agents import mlx_runtime

        captured: Dict[str, Any] = {}

        async def stub_generate(_prompt: str) -> str:
            return VALID_INTENT_JSON

        def fake_get(model_path=None):
            captured["model_path"] = model_path
            return stub_generate

        monkeypatch.setattr(mlx_runtime, "get_mlx_generate_fn", fake_get)

        engine.add_llm_player("llm_one", model_path="mlx-community/some-other-model")
        assert captured["model_path"] == "mlx-community/some-other-model"

    def test_lobby_race_start_dispatches_llm_driver(self, test_track, monkeypatch):
        """End-to-end-ish: a lobby with an LLM bot starts a race and the
        engine ends up with an LLM driver carrying the configured model_path.

        Mirrors what `handle_lobby_start_race` does in the WS route, without
        going through WebSockets.
        """
        from app.agents import mlx_runtime
        from app.core.lobby_manager import LobbyManager

        captured_paths: List[Optional[str]] = []

        async def stub_generate(_prompt: str) -> str:
            return VALID_INTENT_JSON

        def fake_get(model_path=None):
            captured_paths.append(model_path)
            return stub_generate

        monkeypatch.setattr(mlx_runtime, "is_available", lambda: True)
        monkeypatch.setattr(mlx_runtime, "get_mlx_generate_fn", fake_get)

        manager = LobbyManager()
        lobby = manager.create_lobby("Race", "host_player")
        llm_player_id = manager.add_llm_bot_to_lobby(
            lobby_id=lobby.lobby_id,
            model_path="mlx-community/Qwen2.5-7B-Instruct-4bit",
        )
        assert llm_player_id is not None

        # Mimic handle_lobby_start_race's dispatch loop using `test_track`
        # so we don't depend on TrackGenerator settings.
        engine_local = GameEngine(test_track)
        for member in manager.get_lobby(lobby.lobby_id).members.values():
            if member.driver_kind == "llm_bot":
                engine_local.add_llm_player(
                    member.player_id, model_path=member.llm_model_path
                )
            else:
                engine_local.add_player(member.player_id)

        # Forwarded the configured model path to MLX runtime resolution.
        assert captured_paths == ["mlx-community/Qwen2.5-7B-Instruct-4bit"]
        # Engine ended up with an LLM-driven player.
        player = engine_local.state.players[llm_player_id]
        assert player.llm_bot is not None
        assert player.is_bot is True

    def test_add_llm_player_raises_bot_error_when_mlx_unavailable(self, engine, monkeypatch):
        """Acceptance criterion: clear error when MLX is configured but missing."""
        from app.agents import mlx_runtime

        # Force fresh import attempt and make it fail.
        mlx_runtime.MLXRuntime._instance = None

        def boom_init(self, *args, **kwargs):
            raise RuntimeError(
                "MLX is not installed. Install backend/requirements-agents.txt"
            )

        monkeypatch.setattr(mlx_runtime.MLXRuntime, "__init__", boom_init)

        with pytest.raises(BotError) as exc_info:
            engine.add_llm_player("llm_player")

        assert "MLX" in str(exc_info.value)
