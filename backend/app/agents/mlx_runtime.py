"""MLX-backed generation for the LLM strategist (issue #152).

MLX is an optional dependency. This module imports cleanly without it
installed; the runtime check happens only when something tries to use
the model. Install with `pip install -r backend/requirements-agents.txt`
to enable LLM agents.

Default model: Qwen/Qwen2.5-1.5B-Instruct (Q4-quantized variant on the
mlx-community hub). Override with the MLX_MODEL_PATH env var.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import os
from typing import Dict, Optional

logger = logging.getLogger(__name__)


DEFAULT_MODEL_PATH = os.environ.get(
    "MLX_MODEL_PATH",
    "mlx-community/Qwen2.5-1.5B-Instruct-4bit",
)


# Shared single-worker executor across *all* MLXRuntime instances.
# MLX uses a process-wide default Metal stream, so two runtimes (different
# models) running inference on separate threads still collide on the same
# command buffer state (#167 was the symptom on same-model; #170 is the
# same family of bug for different models). Funnelling every generate
# through one OS thread, regardless of model, is the only safe ordering.
#
# Trade-off: with N LLM bots, inference is strictly serial across them.
# At ~300-500 ms per call and 1Hz strategist tick, N=3 bots is the
# practical ceiling before the controller starts running on stale intents.
_MLX_EXECUTOR = concurrent.futures.ThreadPoolExecutor(
    max_workers=1,
    thread_name_prefix="mlx-shared",
)


class MLXRuntime:
    """Per-model_path cached runtime wrapping the mlx-lm model+tokenizer.

    The runtime is loaded once per unique ``model_path`` and kept alive for
    the lifetime of the process. Multiple LLM bots on the same model share
    one runtime; different models load independently. Cache hits skip the
    multi-GB model load.
    """

    _runtimes: Dict[str, "MLXRuntime"] = {}

    def __init__(self, model_path: str = DEFAULT_MODEL_PATH, max_tokens: int = 64) -> None:
        try:
            from mlx_lm import load, generate
        except ImportError as exc:
            raise RuntimeError(
                "MLX is not installed. Install backend/requirements-agents.txt "
                "to enable LLM agents (Apple Silicon only)."
            ) from exc

        logger.info("Loading MLX model: %s", model_path)
        self._model, self._tokenizer = load(model_path)
        self._generate = generate
        self._max_tokens = max_tokens
        logger.info("MLX model loaded")

    async def generate(self, prompt: str) -> str:
        """Async wrapper around the synchronous mlx-lm generate call.

        Routes through the module-level shared single-worker executor
        (see _MLX_EXECUTOR above) so every MLX call across every runtime
        runs on the same OS thread. Concurrent callers queue.
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            _MLX_EXECUTOR,
            lambda: self._generate(
                self._model,
                self._tokenizer,
                prompt=prompt,
                max_tokens=self._max_tokens,
                verbose=False,
            ),
        )


def get_runtime(model_path: Optional[str] = None) -> MLXRuntime:
    """Return the cached MLXRuntime for the given model_path.

    First request for a given path loads the model (slow); subsequent
    requests return the cached instance. ``model_path=None`` resolves to
    ``DEFAULT_MODEL_PATH`` so existing callers see no behavior change.
    """
    path = model_path or DEFAULT_MODEL_PATH
    cached = MLXRuntime._runtimes.get(path)
    if cached is None:
        cached = MLXRuntime(model_path=path)
        MLXRuntime._runtimes[path] = cached
    return cached


def get_mlx_generate_fn(model_path: Optional[str] = None):
    """Return an async generate_fn for the given model_path (default model if None)."""
    return get_runtime(model_path).generate


def is_available() -> bool:
    """Check whether MLX can be imported, without loading a model."""
    try:
        import mlx_lm  # noqa: F401
        return True
    except ImportError:
        return False


# Per-tick generate budget by model size. Measured on an M4 Pro 48 GB:
# 1.5B-Q4 ~0.5s, 3B-Q4 ~1s, 7B-Q4 ~3–5s, 13B-Q4 ~10s+. The numbers below
# leave generous headroom because the first call after model load pays
# Metal command-buffer compilation cost, often 2–3× steady-state.
#
# A miss (model size we can't infer) returns ``_DEFAULT_TIMEOUT_S``, which
# is generous enough to cover the common 1.5B–7B range. The function is
# pure substring-matching — no MLX import, safe to call before/without
# MLX installed.
_DEFAULT_TIMEOUT_S = 15.0
_TIMEOUTS_BY_SIZE_HINT = (
    # Order matters: longest substring wins (32B before 3B, etc.).
    ("32b", 60.0),
    ("30b", 60.0),
    ("14b", 30.0),
    ("13b", 30.0),
    ("8b", 20.0),
    ("7b", 20.0),
    ("3b", 10.0),
    ("1.5b", 5.0),
    ("1.7b", 5.0),
    ("1b", 5.0),
    ("0.5b", 4.0),
)


def estimate_timeout_for_model(model_path: Optional[str]) -> float:
    """Heuristic per-tick generate timeout for the given MLX model path.

    Used by ``add_llm_player`` to plumb a sensible ``timeout_s`` into
    ``LLMStrategist`` without callers having to know what model they're
    racing. Larger models need a much bigger budget than the original
    2-second default, otherwise every tick times out before the model
    can answer and the controller is stuck in fallback cruise (the bug
    that motivated this function).

    The match is a simple lowercased substring scan over the model path.
    Unknown paths get ``_DEFAULT_TIMEOUT_S``.
    """
    if model_path is None:
        return _DEFAULT_TIMEOUT_S
    lower = model_path.lower()
    for hint, timeout in _TIMEOUTS_BY_SIZE_HINT:
        if hint in lower:
            return timeout
    return _DEFAULT_TIMEOUT_S
