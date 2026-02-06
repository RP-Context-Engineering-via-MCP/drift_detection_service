"""Application constants."""

from enum import Enum


class BehaviorState(str, Enum):
    """Behavior lifecycle states."""

    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"
    FLAGGED = "FLAGGED"


class ResolutionAction(str, Enum):
    """Possible resolution actions for behavior conflicts."""

    SUPERSEDE = "SUPERSEDE"
    REINFORCE = "REINFORCE"
    INSERT = "INSERT"
    IGNORE = "IGNORE"


class DriftType(str, Enum):
    """Types of behavioral drift."""

    POLARITY_SHIFT = "POLARITY_SHIFT"  # e.g., "like Python" -> "hate Python"
    TARGET_SHIFT = "TARGET_SHIFT"  # e.g., "prefer Python" -> "prefer Go"
    REFINEMENT = "REFINEMENT"  # e.g., "prefer JS" -> "prefer TS for backend"


class Intent(str, Enum):
    """Canonical intent types."""

    PREFERENCE = "PREFERENCE"
    DISLIKE = "DISLIKE"
    GOAL = "GOAL"
    HABIT = "HABIT"
    BELIEF = "BELIEF"
    SKILL = "SKILL"


class Polarity(str, Enum):
    """Sentiment polarity."""

    POSITIVE = "POSITIVE"
    NEGATIVE = "NEGATIVE"
    NEUTRAL = "NEUTRAL"
