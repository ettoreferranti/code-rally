"""GET /llm-models — return the curated model preset list for the Tinker UI.

Source of truth is `backend/app/agents/llm_model_presets.json`. Restart
the server after editing the JSON to pick up changes (the loader caches
for the process lifetime).
"""

from typing import List

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from app.agents.model_presets import load_presets

router = APIRouter(prefix="/llm-models", tags=["llm-models"])


class ModelPresetResponse(BaseModel):
    # `model_path` would otherwise trigger Pydantic v2's protected
    # `model_` namespace warning. We're using it as a user-facing field,
    # not a Pydantic config attribute.
    model_config = ConfigDict(protected_namespaces=())

    label: str
    model_path: str
    description: str
    default: bool


@router.get("", response_model=List[ModelPresetResponse])
async def list_model_presets() -> List[ModelPresetResponse]:
    """Return the curated MLX model presets used by the Tinker UI."""
    return [
        ModelPresetResponse(**preset.to_dict())
        for preset in load_presets()
    ]
