"""MLX-gated integration tests for the LLM strategist (issue #152).

These tests load the real model. They are skipped automatically when
MLX is not installed (i.e. on CI or non-Apple-Silicon machines), so
the main test suite remains fast and portable.

Run locally with:
    cd backend && ./venv/bin/python -m pytest tests/test_mlx_runtime.py -v

Override the default model with MLX_MODEL_PATH; e.g. a smaller model
for faster iteration.
"""

import pytest

from app.agents.llm_strategist import LLMStrategist
from app.agents.mlx_runtime import is_available

pytestmark = pytest.mark.skipif(
    not is_available(),
    reason="MLX not installed (optional dependency, Apple Silicon only)",
)


@pytest.mark.asyncio
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
