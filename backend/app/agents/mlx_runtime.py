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
