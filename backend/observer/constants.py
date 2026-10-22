"""
Observer constants and threshold configurations.
"""
from __future__ import annotations

# Relationship dimensions tracked per directed pair (A -> B)
DIMENSIONS = ("trust", "rapport", "tension", "respect", "power_balance")

# Valid ranges for dimensions
BOUNDS: dict[str, tuple[float, float]] = {
    "trust": (0.0, 100.0),
    "rapport": (0.0, 100.0),
    "tension": (0.0, 100.0),
    "respect": (0.0, 100.0),
    "power_balance": (-100.0, 100.0),
}

# Neutral default starting values
NEUTRAL_VALUES: dict[str, float] = {
    "trust": 50.0,
    "rapport": 50.0,
    "tension": 50.0,
    "respect": 50.0,
    "power_balance": 0.0,
}

# Delta clamping: maximum change per dimension per turn
MAX_DELTA: float = 10.0

# Exponential smoothing factor: alpha in [0, 1] where 1.0 = raw delta, 0.0 = no update
SMOOTHING_ALPHA: float = 0.4

# Context window: number of past turns fed to the observer turn prompt
OBSERVER_HISTORY_WINDOW: int = 6

# Interval for updating rolling narrative summary
SUMMARY_REFRESH_INTERVAL: int = 4

# Realism metric keys evaluated in ConversationScorecard (scale 1.0 - 10.0)
REALISM_METRIC_KEYS = (
    "persona_consistency",
    "emotional_realism",
    "conversational_coherence",
    "goal_alignment",
    "conflict_realism",
    "social_plausibility",
    "overall_realism",
)
