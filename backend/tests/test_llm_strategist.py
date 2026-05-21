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

    def test_legacy_three_field_json_parses_with_defaults(self):
        # Backward compat: old user-saved prompts emit only the original
        # three fields. They MUST still parse, with the new fields taking
        # their defaults (no nitro, no targeting, tactic="race").
        intent = Intent(target_speed_kmh=80, racing_line_offset_m=0, aggression=0.5)
        assert intent.use_nitro is False
        assert intent.target_opponent_index is None
        assert intent.tactic == "race"

    def test_accepts_use_nitro(self):
        intent = Intent(
            target_speed_kmh=160,
            racing_line_offset_m=0,
            aggression=0.8,
            use_nitro=True,
        )
        assert intent.use_nitro is True

    def test_accepts_target_opponent_and_tactic(self):
        intent = Intent(
            target_speed_kmh=130,
            racing_line_offset_m=-2,
            aggression=0.8,
            target_opponent_index=0,
            tactic="overtake",
        )
        assert intent.target_opponent_index == 0
        assert intent.tactic == "overtake"

    def test_rejects_invalid_tactic(self):
        with pytest.raises(Exception):
            Intent(
                target_speed_kmh=80,
                racing_line_offset_m=0,
                aggression=0.5,
                tactic="rampage",  # not in the Literal set
            )

    def test_rejects_out_of_range_target_opponent(self):
        # Observation exposes 2 slots (0 and 1). Anything else is rejected.
        with pytest.raises(Exception):
            Intent(
                target_speed_kmh=80,
                racing_line_offset_m=0,
                aggression=0.5,
                target_opponent_index=2,
            )
        with pytest.raises(Exception):
            Intent(
                target_speed_kmh=80,
                racing_line_offset_m=0,
                aggression=0.5,
                target_opponent_index=-1,
            )


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

    def test_out_of_range_is_clamped_not_dropped(self):
        # Updated from the old "drops on out-of-range" assertion. Small
        # MLX models routinely overshoot the documented bounds; we now
        # clamp into the schema range instead of dropping the entire
        # intent so the controller doesn't get starved into fallback.
        raw = '{"target_speed_kmh": 80, "racing_line_offset_m": 0, "aggression": 5}'
        intent = _parse_intent(raw)
        assert intent is not None
        assert intent.aggression == 1.0

    def test_parses_first_object_when_model_concatenates_outputs(self):
        """Observed from Qwen2.5-1.5B during #162 diagnosis: the model
        keeps emitting the same JSON object over and over, often truncated
        at the end. The parser must take the FIRST complete object.
        """
        raw = (
            '{"target_speed_kmh": 44, "racing_line_offset_m": 0, "aggression": 0.5} '
            '{"target_speed_kmh": 44, "racing_line_offset_m": 0, "aggression": 0.5} '
            '{"target_speed_kmh":'
        )
        intent = _parse_intent(raw)
        assert intent is not None
        assert intent.target_speed_kmh == 44
        assert intent.racing_line_offset_m == 0
        assert intent.aggression == 0.5

    def test_clamps_offset_below_lower_bound(self):
        # Real-world observed output: small Qwen models emit values like
        # racing_line_offset_m=-52 or -130 despite the prompt saying
        # "-10 to 10". Pre-clamp keeps the intent usable instead of
        # silently dropping it.
        raw = (
            '{"target_speed_kmh": 113, "racing_line_offset_m": -130, '
            '"aggression": 0.9, "target_opponent_index": 0, "tactic": "race"}'
        )
        intent = _parse_intent(raw)
        assert intent is not None
        # Schema lower bound is -20.0 (see Intent.racing_line_offset_m).
        assert intent.racing_line_offset_m == -20.0
        # Other fields untouched.
        assert intent.target_speed_kmh == 113
        assert intent.aggression == 0.9

    def test_clamps_offset_above_upper_bound(self):
        raw = (
            '{"target_speed_kmh": 169, "racing_line_offset_m": 88, '
            '"aggression": 0.9}'
        )
        intent = _parse_intent(raw)
        assert intent is not None
        assert intent.racing_line_offset_m == 20.0

    def test_clamps_target_speed_above_bound(self):
        # 1000 km/h is silly; clamp to schema max (400).
        raw = '{"target_speed_kmh": 1000, "racing_line_offset_m": 0, "aggression": 0.5}'
        intent = _parse_intent(raw)
        assert intent is not None
        assert intent.target_speed_kmh == 400.0

    def test_clamps_aggression_above_bound(self):
        raw = '{"target_speed_kmh": 100, "racing_line_offset_m": 0, "aggression": 1.7}'
        intent = _parse_intent(raw)
        assert intent is not None
        assert intent.aggression == 1.0

    def test_clamps_negative_aggression_to_zero(self):
        raw = '{"target_speed_kmh": 100, "racing_line_offset_m": 0, "aggression": -0.3}'
        intent = _parse_intent(raw)
        assert intent is not None
        assert intent.aggression == 0.0

    def test_in_range_values_are_not_modified(self):
        raw = '{"target_speed_kmh": 120, "racing_line_offset_m": -7.5, "aggression": 0.6}'
        intent = _parse_intent(raw)
        assert intent is not None
        # No clamping fired ⇒ values exactly as supplied.
        assert intent.target_speed_kmh == 120
        assert intent.racing_line_offset_m == -7.5
        assert intent.aggression == 0.6

    def test_clamping_still_drops_intent_below_min_target(self):
        # The min-target floor runs AFTER clamping. A target of 5 km/h is
        # in [0, 400] schema bounds, but below the strategist's safety
        # floor — keep the old "drop and hold last good intent" behaviour
        # so the car never converges to a near-stop.
        raw = '{"target_speed_kmh": 5, "racing_line_offset_m": 0, "aggression": 0.5}'
        assert _parse_intent(raw) is None

    def test_clamp_does_not_choke_on_non_numeric_values(self):
        # Defensive: if the model emits a string for a numeric field, the
        # pre-clamp must leave it alone (it isn't numeric → no clamp).
        # Pydantic's coercion may still accept it; in that case fine,
        # we just want the clamp to not crash on the unexpected type.
        raw = '{"target_speed_kmh": "150", "racing_line_offset_m": 0, "aggression": 0.5}'
        intent = _parse_intent(raw)
        # Pydantic coerces "150" → 150 ⇒ we expect a parsed intent here.
        assert intent is not None
        assert intent.target_speed_kmh == 150

    def test_parses_first_object_with_trailing_prose(self):
        raw = (
            '{"target_speed_kmh": 80, "racing_line_offset_m": 0, "aggression": 0.5}\n'
            "Note: maintain steady speed through the corner."
        )
        intent = _parse_intent(raw)
        assert intent is not None
        assert intent.target_speed_kmh == 80

    def test_rejects_intent_with_target_below_racing_floor(self):
        """Observed during #162 diagnosis: Qwen2.5-1.5B on a wet stage
        converges to `target_speed_kmh=0`, parking the car. We reject
        intents below a racing floor so the strategist holds the last
        good intent and the bot keeps racing."""
        # 0 means "stop" — the original failure mode.
        assert _parse_intent(
            '{"target_speed_kmh": 0, "racing_line_offset_m": 0, "aggression": 0}'
        ) is None
        # 15 km/h is also too slow to race (below the controller's own fallback).
        assert _parse_intent(
            '{"target_speed_kmh": 15, "racing_line_offset_m": 0, "aggression": 0.5}'
        ) is None

    def test_accepts_intent_at_racing_floor(self):
        intent = _parse_intent(
            '{"target_speed_kmh": 30, "racing_line_offset_m": 0, "aggression": 0.5}'
        )
        assert intent is not None
        assert intent.target_speed_kmh == 30


# ===== build_prompt =====


class TestBuildPrompt:
    def test_includes_observation(self):
        prompt = build_prompt("speed=80 km/h, next checkpoint 100m ahead")
        assert "speed=80 km/h" in prompt
        assert "next checkpoint 100m ahead" in prompt

    def test_custom_strategy_overrides_default_persona(self):
        # Custom strategy text replaces the default persona/heuristics.
        custom = "You are a CRAZY rally driver."
        prompt = build_prompt(
            "speed=80 km/h, surface=ice",
            system_prompt=custom,
        )
        assert custom in prompt
        # The default persona must NOT be present when a custom one is given.
        assert "Top speed is around 180 km/h" not in prompt
        # Observation still flows through.
        assert "speed=80 km/h" in prompt

    def test_protocol_is_always_appended_even_with_custom_strategy(self):
        # The JSON I/O contract must reach the model regardless of what
        # the user wrote in their strategy — otherwise a forgotten
        # JSON instruction silently breaks the bot.
        prompt = build_prompt(
            "speed=10 km/h",
            system_prompt="Drive carefully.",
        )
        assert "target_speed_kmh" in prompt
        assert "racing_line_offset_m" in prompt
        assert "aggression" in prompt
        assert "No prose, no markdown, no code fences" in prompt

    def test_default_strategy_is_exported(self):
        # Tinker UI pre-fills the strategy textarea with this constant.
        from app.agents.llm_strategist import DEFAULT_STRATEGY_PROMPT

        assert isinstance(DEFAULT_STRATEGY_PROMPT, str)
        assert "rally" in DEFAULT_STRATEGY_PROMPT.lower()
        # The default strategy is strategy-only — no protocol leakage.
        assert "target_speed_kmh" not in DEFAULT_STRATEGY_PROMPT
        assert "JSON" not in DEFAULT_STRATEGY_PROMPT

    def test_instructs_json_only_output(self):
        prompt = build_prompt("anything")
        # Sanity-check the prompt steers the model toward JSON
        assert "JSON" in prompt
        assert "target_speed_kmh" in prompt

    def test_protocol_documents_optional_intent_fields(self):
        # New tactical fields must be documented in the protocol so the
        # model can actually emit them. The defaults make these optional.
        prompt = build_prompt("anything")
        assert "use_nitro" in prompt
        assert "target_opponent_index" in prompt
        assert "tactic" in prompt
        # The tactic enum values must all be visible to the model.
        for tactic in ("race", "overtake", "block", "pit"):
            assert tactic in prompt

    def test_default_strategy_mentions_racing_pedagogy(self):
        # The new default strategy teaches braking/apex/exit and surface
        # adjustments. Loose checks so wording can evolve.
        from app.agents.llm_strategist import DEFAULT_STRATEGY_PROMPT

        lower = DEFAULT_STRATEGY_PROMPT.lower()
        assert "brake" in lower
        assert "apex" in lower
        assert "surface" in lower or "gravel" in lower
        assert "nitro" in lower


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


# ===== LLMStrategist intent timestamp (#156) =====


class TestStrategistIntentTimestamp:
    """latest_intent_with_ts() returns (intent, ts) so consumers can detect stale intents."""

    @pytest.mark.asyncio
    async def test_returns_none_pair_before_any_intent(self):
        strategist = LLMStrategist(_make_fake_generate(["{}"]))
        intent, ts = strategist.latest_intent_with_ts()
        assert intent is None
        assert ts is None

    @pytest.mark.asyncio
    async def test_records_timestamp_when_intent_stored(self):
        import time as _time

        good = '{"target_speed_kmh": 90, "racing_line_offset_m": 0, "aggression": 0.5}'
        strategist = LLMStrategist(_make_fake_generate([good]))
        strategist.set_observation("obs")

        before = _time.time()
        await strategist.tick_once()
        after = _time.time()

        intent, ts = strategist.latest_intent_with_ts()
        assert intent is not None
        assert ts is not None
        assert before <= ts <= after

    @pytest.mark.asyncio
    async def test_preserves_previous_ts_on_parse_failure(self):
        good = '{"target_speed_kmh": 60, "racing_line_offset_m": 0, "aggression": 0.3}'
        bad = "garbage"
        strategist = LLMStrategist(_make_fake_generate([good, bad]))
        strategist.set_observation("obs")

        await strategist.tick_once()
        _, ts_first = strategist.latest_intent_with_ts()
        assert ts_first is not None

        await strategist.tick_once()  # fails to parse
        intent, ts_second = strategist.latest_intent_with_ts()
        # ts unchanged because the previous good intent is still latest
        assert intent.target_speed_kmh == 60
        assert ts_second == ts_first


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
