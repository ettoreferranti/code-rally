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
        # All inference on this runtime runs on a single dedicated worker
        # thread. Two reasons (#163, #167):
        #   1. The executor's `max_workers=1` queue naturally serialises
        #      concurrent callers, so we don't need a separate asyncio.Lock.
        #   2. Metal command-buffer state is tied to thread identity for
        #      some operations; consecutive `asyncio.to_thread(...)` calls
        #      would bounce between pool threads and trip Metal asserts.
        #      Pinning to one thread keeps the GPU context consistent.
        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix=f"mlx-runtime[{model_path}]",
        )
        logger.info("MLX model loaded")

    async def generate(self, prompt: str) -> str:
        """Async wrapper around the synchronous mlx-lm generate call.

        Routes through the runtime's dedicated single-worker executor so
        every generate runs on the same OS thread and concurrent callers
        queue up (no separate lock needed).
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor,
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
