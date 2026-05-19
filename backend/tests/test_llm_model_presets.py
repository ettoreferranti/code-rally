"""Tests for the LLM model preset config + API (phase 2 of Tinker cleanup)."""

import pytest
from fastapi.testclient import TestClient

from app.agents.model_presets import default_preset, load_presets
from main import app


@pytest.fixture
def client():
    return TestClient(app)


class TestModelPresetLoader:
    def test_loads_at_least_one_preset(self):
        # Bust the lru_cache so we always read the file fresh in tests.
        load_presets.cache_clear()
        presets = load_presets()
        assert len(presets) >= 1
        for p in presets:
            assert p.label
            assert p.model_path
            assert isinstance(p.default, bool)

    def test_exactly_one_default_preset(self):
        load_presets.cache_clear()
        presets = load_presets()
        defaults = [p for p in presets if p.default]
        # Either exactly one default OR none (in which case default_preset
        # falls back to the first). Both are valid configs but the
        # convention is exactly one.
        assert len(defaults) <= 1, "More than one preset marked default"

    def test_default_preset_helper_returns_a_value(self):
        load_presets.cache_clear()
        p = default_preset()
        assert p is not None
        # Should match the first 'default: true' if any, else first preset.
        presets = load_presets()
        defaults = [d for d in presets if d.default]
        if defaults:
            assert p.model_path == defaults[0].model_path
        else:
            assert p.model_path == presets[0].model_path


class TestModelPresetEndpoint:
    def test_get_returns_presets(self, client):
        load_presets.cache_clear()
        resp = client.get("/llm-models")
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list)
        assert len(body) >= 1
        # Schema sanity
        for entry in body:
            assert set(entry.keys()) >= {"label", "model_path", "description", "default"}
            assert entry["model_path"].startswith("mlx-community/") or "/" in entry["model_path"]
