"""
Track generation endpoints.

Provides API for procedurally generating rally tracks with
containment boundaries and obstacles.
"""

from fastapi import APIRouter, Query
from typing import Optional

from app.core.track import TrackGenerator, SurfaceType

router = APIRouter()


@router.post("/tracks/generate")
async def generate_track(
    difficulty: str = Query(default="medium", description="Track difficulty (easy, medium, hard)"),
    seed: Optional[int] = Query(default=None, description="Random seed for reproducible tracks")
) -> dict:
    """
    Generate a new procedural rally track.

    Args:
        difficulty: Track difficulty level ("easy", "medium", "hard")
        seed: Optional random seed for reproducible generation

    Returns:
        dict: Complete track data including segments, checkpoints, containment boundaries, and obstacles

    Example response:
        {
            "segments": [...],
            "checkpoints": [...],
            "start_position": [x, y],
            "start_heading": 0.0,
            "finish_position": [x, y],
            "finish_heading": 1.57,
            "total_length": 2500.0,
            "is_looping": false,
            "containment": {
                "left_points": [[x1, y1], [x2, y2], ...],
                "right_points": [[x1, y1], [x2, y2], ...]
            },
            "obstacles": [
                {"position": [x, y], "radius": 10.0, "type": "rock"},
                ...
            ]
        }
    """
    # Create generator with optional seed
    generator = TrackGenerator(seed=seed)

    # Generate track
    track = generator.generate(difficulty=difficulty)

    # Convert to JSON-serializable format
    return {
        "segments": [
            {
                "start": {
                    "x": seg.start.x,
                    "y": seg.start.y,
                    "width": seg.start.width,
                    "surface": seg.start.surface.value
                },
                "end": {
                    "x": seg.end.x,
                    "y": seg.end.y,
                    "width": seg.end.width,
                    "surface": seg.end.surface.value
                },
                "control1": list(seg.control1) if seg.control1 else None,
                "control2": list(seg.control2) if seg.control2 else None
            }
            for seg in track.segments
        ],
        "checkpoints": [
            {
                "position": list(cp.position),
                "angle": cp.angle,
                "width": cp.width,
                "index": cp.index
            }
            for cp in track.checkpoints
        ],
        "start_position": list(track.start_position),
        "start_heading": track.start_heading,
        "finish_position": list(track.finish_position),
        "finish_heading": track.finish_heading,
        "total_length": track.total_length,
        "is_looping": track.is_looping,
        "containment": {
            "left_points": track.containment.left_points,
            "right_points": track.containment.right_points
        } if track.containment else None,
        "obstacles": [
            {
                "position": list(obs.position),
                "radius": obs.radius,
                "type": obs.type
            }
            for obs in track.obstacles
        ]
    }
