"""
Join code generator for shareable lobby codes.

Generates memorable codes in the format: ADJECTIVE-NOUN-NUMBER
Example: FAST-TIGER-42
"""

import random

# Curated lists for memorable codes
ADJECTIVES = [
    "FAST", "QUICK", "SWIFT", "RAPID", "TURBO",
    "BLUE", "RED", "GREEN", "GOLD", "SILVER",
    "WILD", "MEGA", "SUPER", "ULTRA", "HYPER",
    "BOLD", "BRAVE", "EPIC", "COOL", "SLICK",
]

NOUNS = [
    "TIGER", "LION", "EAGLE", "SHARK", "WOLF",
    "DRAGON", "FALCON", "VIPER", "RACER", "RALLY",
    "STORM", "BLAZE", "THUNDER", "LIGHTNING", "COMET",
    "ROCKET", "TURBO", "NITRO", "SPEED", "DRIFT",
]


def generate_join_code() -> str:
    """
    Generate a unique, memorable join code.

    Format: ADJECTIVE-NOUN-NUMBER
    Example: FAST-TIGER-42

    Returns:
        A random join code string
    """
    adjective = random.choice(ADJECTIVES)
    noun = random.choice(NOUNS)
    number = random.randint(10, 99)

    return f"{adjective}-{noun}-{number}"


def is_valid_join_code(code: str) -> bool:
    """
    Validate join code format.

    Args:
        code: Code to validate

    Returns:
        True if code matches expected format
    """
    if not code:
        return False

    parts = code.upper().split("-")
    if len(parts) != 3:
        return False

    adjective, noun, number = parts

    # Check each part
    if adjective not in ADJECTIVES:
        return False
    if noun not in NOUNS:
        return False

    try:
        num = int(number)
        if num < 10 or num > 99:
            return False
    except ValueError:
        return False

    return True
