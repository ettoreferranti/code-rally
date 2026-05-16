"""LLM-driven agent infrastructure (issue #151 / #152).

This package implements the trusted-code side of the two-tier LLM agent:
a high-rate deterministic controller will consume the latest `Intent`
produced by `LLMStrategist`, which itself runs at ~1Hz on top of a
pluggable `generate_fn` (MLX in production, mocks in tests).

Public API:
    - Intent: the structured driving intent schema
    - LLMStrategist: async runner that turns observations into Intents
    - MLXRuntime / get_mlx_generate_fn: optional MLX-backed generation
"""

from app.agents.intent import Intent
from app.agents.llm_strategist import LLMStrategist

__all__ = ["Intent", "LLMStrategist"]
