"""LLM model preset loader.

Reads `llm_model_presets.json` next to this module and exposes it as a
list of typed entries for the API layer and the Tinker UI. Edit the
JSON file to change which presets are offered; no code change needed.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)


_PRESETS_PATH = Path(__file__).resolve().parent / "llm_model_presets.json"


@dataclass(frozen=True)
class ModelPreset:
    label: str
    model_path: str
    description: str
    default: bool

    def to_dict(self) -> dict:
        return {
            "label": self.label,
            "model_path": self.model_path,
            "description": self.description,
            "default": self.default,
        }


@lru_cache(maxsize=1)
def load_presets() -> List[ModelPreset]:
    """Read and cache the preset list. Cached for the process lifetime.

    Restart the server (or call `load_presets.cache_clear()`) after
    editing the JSON to see new entries.
    """
    if not _PRESETS_PATH.exists():
        logger.warning("LLM model presets file not found: %s", _PRESETS_PATH)
        return []

    try:
        data = json.loads(_PRESETS_PATH.read_text())
    except json.JSONDecodeError:
        logger.exception("Failed to parse %s — falling back to empty list", _PRESETS_PATH)
        return []

    raw_presets = data.get("presets", [])
    presets: List[ModelPreset] = []
    for entry in raw_presets:
        try:
            presets.append(
                ModelPreset(
                    label=entry["label"],
                    model_path=entry["model_path"],
                    description=entry.get("description", ""),
                    default=bool(entry.get("default", False)),
                )
            )
        except KeyError:
            logger.warning("Skipping malformed preset entry: %r", entry)
    return presets


def default_preset() -> ModelPreset | None:
    """Return the preset marked `default: true`, or the first one, or None."""
    presets = load_presets()
    for preset in presets:
        if preset.default:
            return preset
    return presets[0] if presets else None
