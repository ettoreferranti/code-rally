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
async def test_generate_pins_across_runtimes_to_one_thread(monkeypatch):
    """Two MLXRuntime instances must share a single worker thread (#170).

    MLX appears to use a process-wide default Metal context, so two
    runtimes (different models) on two threads still collide. The fix
    is a module-level shared executor.
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

    monkeypatch.setattr(MLXRuntime, "__init__", stub_init)

    runtime_a = MLXRuntime()
    runtime_b = MLXRuntime()

    # Both runtimes' generate calls, interleaved.
    await asyncio.gather(
        runtime_a.generate("a1"),
        runtime_b.generate("b1"),
        runtime_a.generate("a2"),
        runtime_b.generate("b2"),
    )

    assert len(seen_threads) == 4
    assert len(set(seen_threads)) == 1, (
        f"Cross-runtime inference must share one thread; saw {set(seen_threads)}"
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

    monkeypatch.setattr(MLXRuntime, "__init__", stub_init)

    runtime = MLXRuntime()

    results = await asyncio.gather(runtime.generate("p1"), runtime.generate("p2"))

    assert results == ["stub-output", "stub-output"]
    assert state["max_concurrent"] == 1, (
        "MLXRuntime.generate must serialize concurrent callers — Metal "
        "rejects two simultaneous encodings against the same model."
    )


# ===== Model-aware timeout heuristic =====


class TestEstimateTimeoutForModel:
    """The heuristic that picks a per-tick generate timeout based on the
    MLX model path. A 2 s timeout (the old default) silently broke 7B+
    models because every tick timed out before the model could answer.
    """

    def test_default_when_path_is_none(self):
        assert mlx_runtime.estimate_timeout_for_model(None) == 15.0

    def test_default_when_path_has_no_size_hint(self):
        assert (
            mlx_runtime.estimate_timeout_for_model(
                "mlx-community/Some-Mystery-Model"
            )
            == 15.0
        )

    def test_small_model_gets_short_timeout(self):
        assert (
            mlx_runtime.estimate_timeout_for_model(
                "mlx-community/Qwen2.5-1.5B-Instruct-4bit"
            )
            == 5.0
        )

    def test_three_b_model_gets_medium_timeout(self):
        assert (
            mlx_runtime.estimate_timeout_for_model(
                "mlx-community/Qwen2.5-3B-Instruct-4bit"
            )
            == 10.0
        )

    def test_seven_b_model_gets_generous_timeout(self):
        # 7B Q4 first call can take 3-5s on M4 Pro; we want headroom.
        assert (
            mlx_runtime.estimate_timeout_for_model(
                "mlx-community/Qwen2.5-7B-Instruct-4bit"
            )
            == 20.0
        )

    def test_eight_b_model_treated_as_seven_b_class(self):
        # Llama 3.1 8B etc.
        assert (
            mlx_runtime.estimate_timeout_for_model(
                "mlx-community/Meta-Llama-3.1-8B-Instruct-4bit"
            )
            == 20.0
        )

    def test_big_model_gets_long_timeout(self):
        assert (
            mlx_runtime.estimate_timeout_for_model(
                "mlx-community/Qwen2.5-32B-Instruct-4bit"
            )
            == 60.0
        )

    def test_substring_order_picks_32b_over_3b(self):
        # Order in the lookup table matters: "32b" must match before "3b"
        # otherwise the bigger model would get the wrong (too-short) budget.
        # This is a regression guard for the lookup-table ordering.
        assert (
            mlx_runtime.estimate_timeout_for_model("mlx-community/Foo-32B")
            == 60.0
        )

    def test_case_insensitive(self):
        assert (
            mlx_runtime.estimate_timeout_for_model("mlx-community/qwen2.5-7b-q4")
            == 20.0
        )


# ===== Model-label formatter =====


class TestFormatLLMModelLabel:
    """Short, human-readable model labels for the race UI. The goal is
    to let a user with multiple LLM bots in the same race tell at a
    glance which car is which (Qwen 7B vs Qwen 1.5B vs Llama 8B etc.).
    """

    def test_none_returns_generic_llm(self):
        assert mlx_runtime.format_llm_model_label(None) == "LLM"

    def test_empty_string_returns_generic_llm(self):
        assert mlx_runtime.format_llm_model_label("") == "LLM"

    def test_qwen_with_size(self):
        assert (
            mlx_runtime.format_llm_model_label(
                "mlx-community/Qwen2.5-7B-Instruct-4bit"
            )
            == "Qwen 7B"
        )

    def test_qwen_with_decimal_size(self):
        assert (
            mlx_runtime.format_llm_model_label(
                "mlx-community/Qwen2.5-1.5B-Instruct-4bit"
            )
            == "Qwen 1.5B"
        )

    def test_llama_with_size(self):
        assert (
            mlx_runtime.format_llm_model_label(
                "mlx-community/Meta-Llama-3.1-8B-Instruct-4bit"
            )
            == "Llama 8B"
        )

    def test_phi_without_explicit_size_falls_back_to_family(self):
        # Phi-3.5-mini doesn't carry an "NB" token; family alone is fine.
        assert (
            mlx_runtime.format_llm_model_label(
                "mlx-community/Phi-3.5-mini-instruct-4bit"
            )
            == "Phi"
        )

    def test_unknown_path_uses_basename(self):
        assert (
            mlx_runtime.format_llm_model_label("custom/some-research-model")
            == "some-research-model"
        )

    def test_size_without_family_returns_size_only(self):
        assert mlx_runtime.format_llm_model_label("acme/SuperBrain-13B-4bit") == "13B"

    def test_strips_path_prefix(self):
        # Long HuggingFace-style path: take the basename.
        assert (
            mlx_runtime.format_llm_model_label(
                "mlx-community/some-org/Qwen2.5-3B-Instruct-4bit"
            )
            == "Qwen 3B"
        )

    def test_case_insensitive_family_match(self):
        assert (
            mlx_runtime.format_llm_model_label("mlx-community/qwen2.5-7b-q4")
            == "Qwen 7B"
        )

    def test_does_not_confuse_version_with_size(self):
        # Qwen2.5 contains "2.5" but it's a version, not a size. Regex
        # uses \b after B to require the suffix; the version number has
        # no trailing B so it's ignored.
        assert (
            mlx_runtime.format_llm_model_label("mlx-community/Qwen2.5-7B-Instruct")
            == "Qwen 7B"
        )
