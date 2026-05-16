"""Unit tests for the LLM strategist (issue #152).

Covers:
- Intent schema validation
- JSON parsing robustness (well-formed, malformed, missing fields,
  out-of-range values, surrounding noise, code fences)
- tick_once() preserves last-good Intent on parse/validation failure
- Per-call timeout drops the tick without raising
- Generate-fn exceptions are swallowed
- Start/stop lifecycle of the background loop

All tests use an injected fake generate_fn — no MLX required.
A separate MLX-gated integration test lives in test_mlx_runtime.py.
"""

import asyncio
from typing import List

import pytest

from app.agents.intent import Intent
from app.agents.llm_strategist import LLMStrategist, _parse_intent, build_prompt


def _make_fake_generate(responses: List[str]):
    """Return an async generate_fn that yields the given responses in order."""
    iterator = iter(responses)

    async def fake_generate(_prompt: str) -> str:
        try:
            return next(iterator)
        except StopIteration:
            # Repeat the last response indefinitely
            return responses[-1] if responses else ""

    return fake_generate


# ===== Intent schema =====


class TestIntentSchema:
    def test_accepts_valid_intent(self):
        intent = Intent(target_speed_kmh=80, racing_line_offset_m=0.5, aggression=0.6)
        assert intent.target_speed_kmh == 80
        assert intent.racing_line_offset_m == 0.5
        assert intent.aggression == 0.6

    def test_rejects_negative_speed(self):
        with pytest.raises(Exception):
            Intent(target_speed_kmh=-10, racing_line_offset_m=0, aggression=0.5)

    def test_rejects_excessive_aggression(self):
        with pytest.raises(Exception):
            Intent(target_speed_kmh=80, racing_line_offset_m=0, aggression=1.5)

    def test_rejects_offset_out_of_bounds(self):
        with pytest.raises(Exception):
            Intent(target_speed_kmh=80, racing_line_offset_m=999, aggression=0.5)


# ===== Pure parser =====


class TestParseIntent:
    def test_parses_clean_json(self):
        raw = '{"target_speed_kmh": 90, "racing_line_offset_m": -1.0, "aggression": 0.4}'
        intent = _parse_intent(raw)
        assert intent is not None
        assert intent.target_speed_kmh == 90

    def test_parses_with_leading_and_trailing_noise(self):
        raw = (
            "Here is the intent:\n"
            '```json\n{"target_speed_kmh": 75, "racing_line_offset_m": 0, "aggression": 0.5}\n```\n'
            "Good luck!"
        )
        intent = _parse_intent(raw)
        assert intent is not None
        assert intent.target_speed_kmh == 75

    def test_returns_none_on_empty_string(self):
        assert _parse_intent("") is None

    def test_returns_none_when_no_braces(self):
        assert _parse_intent("hello world") is None

    def test_returns_none_on_invalid_json(self):
        # Unclosed quote
        assert _parse_intent('{"target_speed_kmh": "abc, "aggression": 0.5}') is None

    def test_returns_none_on_missing_field(self):
        assert _parse_intent('{"target_speed_kmh": 80}') is None

    def test_returns_none_on_out_of_range(self):
        raw = '{"target_speed_kmh": 80, "racing_line_offset_m": 0, "aggression": 5}'
        assert _parse_intent(raw) is None


# ===== build_prompt =====


class TestBuildPrompt:
    def test_includes_observation(self):
        prompt = build_prompt("speed=80 km/h, next checkpoint 100m ahead")
        assert "speed=80 km/h" in prompt
        assert "next checkpoint 100m ahead" in prompt

    def test_instructs_json_only_output(self):
        prompt = build_prompt("anything")
        # Sanity-check the prompt steers the model toward JSON
        assert "JSON" in prompt
        assert "target_speed_kmh" in prompt


# ===== LLMStrategist.tick_once =====


class TestStrategistTickOnce:
    @pytest.mark.asyncio
    async def test_returns_none_with_no_observation(self):
        strategist = LLMStrategist(_make_fake_generate(["{}"]))
        result = await strategist.tick_once()
        assert result is None
        assert strategist.latest_intent() is None

    @pytest.mark.asyncio
    async def test_produces_intent_from_well_formed_output(self):
        raw = '{"target_speed_kmh": 100, "racing_line_offset_m": 2.0, "aggression": 0.7}'
        strategist = LLMStrategist(_make_fake_generate([raw]))
        strategist.set_observation("dummy obs")

        result = await strategist.tick_once()
        assert result is not None
        assert result.target_speed_kmh == 100
        assert strategist.latest_intent() == result

    @pytest.mark.asyncio
    async def test_preserves_last_good_intent_on_parse_failure(self):
        good = '{"target_speed_kmh": 60, "racing_line_offset_m": 0, "aggression": 0.3}'
        bad = "not a json output"
        strategist = LLMStrategist(_make_fake_generate([good, bad]))
        strategist.set_observation("obs")

        first = await strategist.tick_once()
        assert first is not None
        assert strategist.latest_intent().target_speed_kmh == 60

        second = await strategist.tick_once()
        assert second is None
        # latest_intent must still be the previously good one
        assert strategist.latest_intent().target_speed_kmh == 60

    @pytest.mark.asyncio
    async def test_swallows_generate_fn_exceptions(self):
        async def boom(_prompt: str) -> str:
            raise RuntimeError("model exploded")

        strategist = LLMStrategist(boom)
        strategist.set_observation("obs")

        result = await strategist.tick_once()
        assert result is None
        assert strategist.latest_intent() is None

    @pytest.mark.asyncio
    async def test_timeout_does_not_raise(self):
        async def slow(_prompt: str) -> str:
            await asyncio.sleep(1.0)
            return "{}"

        strategist = LLMStrategist(slow, timeout_s=0.05)
        strategist.set_observation("obs")

        result = await strategist.tick_once()
        assert result is None
        assert strategist.latest_intent() is None

    @pytest.mark.asyncio
    async def test_timeout_preserves_previous_intent(self):
        good = '{"target_speed_kmh": 50, "racing_line_offset_m": 0, "aggression": 0.5}'
        call_count = {"n": 0}

        async def first_fast_then_slow(_prompt: str) -> str:
            call_count["n"] += 1
            if call_count["n"] == 1:
                return good
            await asyncio.sleep(1.0)
            return "{}"

        strategist = LLMStrategist(first_fast_then_slow, timeout_s=0.05)
        strategist.set_observation("obs")

        await strategist.tick_once()
        assert strategist.latest_intent().target_speed_kmh == 50

        await strategist.tick_once()  # this one times out
        assert strategist.latest_intent().target_speed_kmh == 50


# ===== LLMStrategist start/stop lifecycle =====


class TestStrategistLifecycle:
    @pytest.mark.asyncio
    async def test_start_runs_loop_in_background(self):
        good = '{"target_speed_kmh": 70, "racing_line_offset_m": 0, "aggression": 0.5}'
        strategist = LLMStrategist(
            _make_fake_generate([good]),
            tick_interval_s=0.01,
        )
        strategist.set_observation("obs")

        await strategist.start()
        # Give the loop a couple of ticks
        await asyncio.sleep(0.05)
        await strategist.stop()

        assert strategist.latest_intent() is not None
        assert strategist.latest_intent().target_speed_kmh == 70

    @pytest.mark.asyncio
    async def test_stop_is_idempotent(self):
        strategist = LLMStrategist(_make_fake_generate(["{}"]), tick_interval_s=0.01)
        await strategist.start()
        await strategist.stop()
        await strategist.stop()  # second call must not raise

    @pytest.mark.asyncio
    async def test_start_twice_is_noop(self):
        strategist = LLMStrategist(_make_fake_generate(["{}"]), tick_interval_s=0.01)
        await strategist.start()
        task_first = strategist._task
        await strategist.start()
        task_second = strategist._task
        assert task_first is task_second
        await strategist.stop()
