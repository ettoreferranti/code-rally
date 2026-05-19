"""MLX runtime tests.

The end-to-end test that actually loads the model is MLX-gated so the
main suite remains fast and portable on CI / non-Apple-Silicon machines.
The concurrency regression test stubs the inner generate function so it
runs everywhere — it covers behavior the runtime must enforce even
without MLX installed.

Run locally with:
    cd backend && ./venv/bin/python -m pytest tests/test_mlx_runtime.py -v
"""

import asyncio
import time

import pytest

from app.agents.llm_strategist import LLMStrategist
from app.agents import mlx_runtime
from app.agents.mlx_runtime import MLXRuntime, is_available


@pytest.mark.asyncio
@pytest.mark.skipif(
    not is_available(),
    reason="MLX not installed (optional dependency, Apple Silicon only)",
)
async def test_real_mlx_call_returns_parseable_intent():
    """End-to-end: load model, prompt it, parse an Intent.

    Slow: loads the full model on first call. We use a constrained
    observation so even a small model is likely to produce valid JSON.
    """
    from app.agents.mlx_runtime import get_mlx_generate_fn

    strategist = LLMStrategist(get_mlx_generate_fn(), timeout_s=30.0)
    strategist.set_observation(
        "speed: 50 km/h, next checkpoint: 80m straight ahead, "
        "surface: asphalt, no opponents"
    )

    intent = await strategist.tick_once()
    # The model may occasionally fail to produce valid JSON; we accept
    # either a parsed Intent or None (per the strategist's contract).
    # The strong assertion: it must NOT raise.
    if intent is not None:
        assert 0 <= intent.target_speed_kmh <= 400
        assert -20 <= intent.racing_line_offset_m <= 20
        assert 0 <= intent.aggression <= 1


# ===== Concurrency (issue #163) =====


@pytest.mark.asyncio
async def test_generate_pins_to_single_thread(monkeypatch):
    """All generate calls on a given MLXRuntime must run on the same OS
    thread. Metal's command-buffer lifecycle isn't safe across the
    asyncio default thread pool's worker threads — that's #167.

    Stub the inner _generate to capture the thread identity for each
    call, fire several concurrent + serial generates, assert one thread.
    """
    import threading

    seen_threads = []

    def stub_inner_generate(model, tokenizer, prompt, max_tokens, verbose):
        seen_threads.append(threading.get_ident())
        time.sleep(0.01)
        return "ok"

    def stub_init(self, model_path=mlx_runtime.DEFAULT_MODEL_PATH, max_tokens=64):
        self._model = None
        self._tokenizer = None
        self._generate = stub_inner_generate
        self._max_tokens = max_tokens
        # Single-thread executor is owned by the runtime — see __init__
        # in production. Mimic the same here.
        import concurrent.futures
        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="mlx-runtime-test"
        )

    monkeypatch.setattr(MLXRuntime, "__init__", stub_init)

    runtime = MLXRuntime()

    # Serial: three back-to-back calls.
    await runtime.generate("p1")
    await runtime.generate("p2")
    await runtime.generate("p3")

    # Concurrent: gather four more in parallel.
    await asyncio.gather(
        runtime.generate("a"),
        runtime.generate("b"),
        runtime.generate("c"),
        runtime.generate("d"),
    )

    assert len(seen_threads) == 7
    assert len(set(seen_threads)) == 1, (
        f"All generate calls must run on one thread; saw {set(seen_threads)}"
    )


@pytest.mark.asyncio
async def test_generate_serializes_concurrent_calls(monkeypatch):
    """Two concurrent generate() calls on the same MLXRuntime must NOT
    run their inner mlx-lm call in parallel.

    Metal command-buffer semantics blow up if two threads encode against
    the same loaded model simultaneously, which is exactly what happens
    today with two LLM bots sharing a runtime via the per-`model_path`
    cache (issue #163).

    We stub the inner _generate to track concurrent in-flight count and
    assert the runtime queues callers so the max-concurrent count stays
    at 1.
    """
    state = {"in_flight": 0, "max_concurrent": 0}

    def stub_inner_generate(model, tokenizer, prompt, max_tokens, verbose):
        state["in_flight"] += 1
        state["max_concurrent"] = max(state["max_concurrent"], state["in_flight"])
        # Simulate model latency so a second concurrent caller has time
        # to enter if no lock is enforcing serialization.
        time.sleep(0.05)
        state["in_flight"] -= 1
        return "stub-output"

    def stub_init(self, model_path=mlx_runtime.DEFAULT_MODEL_PATH, max_tokens=64):
        # Skip the real `mlx_lm.load` — we only need the surface that
        # `generate()` consumes.
        self._model = None
        self._tokenizer = None
        self._generate = stub_inner_generate
        self._max_tokens = max_tokens
        import concurrent.futures
        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="mlx-runtime-test"
        )

    monkeypatch.setattr(MLXRuntime, "__init__", stub_init)

    runtime = MLXRuntime()

    results = await asyncio.gather(runtime.generate("p1"), runtime.generate("p2"))

    assert results == ["stub-output", "stub-output"]
    assert state["max_concurrent"] == 1, (
        "MLXRuntime.generate must serialize concurrent callers — Metal "
        "rejects two simultaneous encodings against the same model."
    )
