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
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


DEFAULT_MODEL_PATH = os.environ.get(
    "MLX_MODEL_PATH",
    "mlx-community/Qwen2.5-1.5B-Instruct-4bit",
)


class MLXRuntime:
    """Lazily-loaded singleton wrapping the mlx-lm model+tokenizer."""

    _instance: Optional["MLXRuntime"] = None

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
        """Async wrapper around the synchronous mlx-lm generate call."""
        return await asyncio.to_thread(
            self._generate,
            self._model,
            self._tokenizer,
            prompt=prompt,
            max_tokens=self._max_tokens,
            verbose=False,
        )


def get_runtime() -> MLXRuntime:
    """Return the process-wide MLXRuntime singleton (loads on first call)."""
    if MLXRuntime._instance is None:
        MLXRuntime._instance = MLXRuntime()
    return MLXRuntime._instance


def get_mlx_generate_fn():
    """Return an async generate_fn suitable for LLMStrategist."""
    runtime = get_runtime()
    return runtime.generate


def is_available() -> bool:
    """Check whether MLX can be imported, without loading a model."""
    try:
        import mlx_lm  # noqa: F401
        return True
    except ImportError:
        return False
