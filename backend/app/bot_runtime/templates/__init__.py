"""
Bot templates for CodeRally.

This module contains starter templates to help new bot developers learn the API.
Each template demonstrates different racing strategies and API features.
"""

# Template metadata for frontend integration
TEMPLATES = [
    {
        "id": "simple_follower",
        "name": "Simple Follower",
        "difficulty": 1,
        "description": "Beginner-friendly bot that uses raycasts to follow the track. Great starting point for learning the basics.",
        "features": ["Raycast navigation", "Basic steering", "Obstacle avoidance"],
        "file": "simple_follower.py"
    },
    {
        "id": "surface_aware",
        "name": "Surface Aware Racer",
        "difficulty": 2,
        "description": "Intermediate bot that adapts driving style based on surface conditions (asphalt, gravel, ice, wet).",
        "features": ["Surface detection", "Speed adaptation", "Strategic nitro usage"],
        "file": "surface_aware.py"
    },
    {
        "id": "checkpoint_navigator",
        "name": "Checkpoint Navigator",
        "difficulty": 3,
        "description": "Advanced bot using trigonometry and checkpoint positions for precise navigation.",
        "features": ["Checkpoint navigation", "Angle calculations", "Predictive steering"],
        "file": "checkpoint_navigator.py"
    },
    {
        "id": "aggressive_racer",
        "name": "Aggressive Racer",
        "difficulty": 4,
        "description": "Expert-level bot combining all strategies: checkpoint navigation, surface adaptation, opponent tracking, and aggressive overtaking.",
        "features": ["Multi-strategy", "Opponent awareness", "Risk management", "Dynamic optimization"],
        "file": "aggressive_racer.py"
    }
]


def get_template_list():
    """
    Get list of available templates.

    Returns:
        list: Template metadata dictionaries
    """
    return TEMPLATES


def get_template_code(template_id: str) -> str:
    """
    Get the source code for a template bot.

    Args:
        template_id: Template identifier (e.g., "simple_follower")

    Returns:
        str: Template source code

    Raises:
        ValueError: If template_id is not found
    """
    import os

    # Find template metadata
    template = next((t for t in TEMPLATES if t["id"] == template_id), None)
    if not template:
        raise ValueError(f"Template '{template_id}' not found")

    # Read template file
    template_dir = os.path.dirname(__file__)
    template_path = os.path.join(template_dir, template["file"])

    with open(template_path, 'r') as f:
        return f.read()
