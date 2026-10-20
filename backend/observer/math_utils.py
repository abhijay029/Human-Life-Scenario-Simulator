"""
Pure math and trajectory utility functions for the Observer Agent.
Includes delta clamping, exponential smoothing (EMA), linear regression slope,
and trajectory classification.
"""
from __future__ import annotations

from typing import Literal
from .constants import (
    BOUNDS,
    DIMENSIONS,
    MAX_DELTA,
    SMOOTHING_ALPHA,
    SLOPE_THRESHOLD_SIGNIFICANT,
)
from .schemas import DyadState, TurningPoint


def apply_dyad_deltas(
    current: DyadState,
    deltas: dict[str, float],
    clamp_limit: float = MAX_DELTA,
    alpha: float = SMOOTHING_ALPHA,
    reason: str = "",
    turn_index: int = 0,
    turning_point_threshold: float = 5.0,
) -> tuple[DyadState, list[TurningPoint]]:
    """
    Applies bounded deltas with exponential smoothing to a DyadState.

    1. Raw delta is clamped to [-clamp_limit, clamp_limit] (default +/-10.0).
    2. EMA smoothing applies: effective_delta = alpha * clamped_delta.
    3. New value is clamped to [min_bound, max_bound].
    4. If |clamped_delta| >= turning_point_threshold, creates a TurningPoint.
    """
    updates: dict[str, float] = {}
    turning_points: list[TurningPoint] = []

    for dim in DIMENSIONS:
        raw_delta = float(deltas.get(dim, 0.0))
        clamped_delta = max(-clamp_limit, min(clamp_limit, raw_delta))
        effective_delta = alpha * clamped_delta

        current_val = getattr(current, dim)
        min_bound, max_bound = BOUNDS[dim]
        new_val = max(min_bound, min(max_bound, round(current_val + effective_delta, 2)))
        updates[dim] = new_val

        if abs(clamped_delta) >= turning_point_threshold:
            tp_reason = reason.strip() if reason else f"Significant shift in {dim}"
            turning_points.append(
                TurningPoint(
                    turn_index=turn_index,
                    dimension=dim,
                    delta=round(effective_delta, 2),
                    value_after=new_val,
                    reason=tp_reason,
                )
            )

    new_state = current.model_copy(update=updates)
    return new_state, turning_points


def calculate_slope(values: list[float]) -> float:
    """
    Computes ordinary least squares linear regression slope over a sequence of values.
    Returns 0.0 if fewer than 2 values are provided.
    """
    n = len(values)
    if n < 2:
        return 0.0

    # x values are 0, 1, ..., n-1
    x_mean = (n - 1) / 2.0
    y_mean = sum(values) / n

    numerator = sum((i - x_mean) * (y - y_mean) for i, y in enumerate(values))
    denominator = sum((i - x_mean) ** 2 for i in range(n))

    if denominator == 0.0:
        return 0.0

    return round(numerator / denominator, 4)


def classify_trajectory(
    dimension: str,
    slope: float,
    threshold: float = SLOPE_THRESHOLD_SIGNIFICANT,
) -> Literal["improving", "stable", "deteriorating"]:
    """
    Classifies a dimension's trajectory based on linear slope and polarity.

    - For tension: rising tension (> threshold) is deteriorating; falling is improving.
    - For trust, rapport, respect, power_balance: positive slope (> threshold) is improving;
      negative slope (< -threshold) is deteriorating.
    - Slopes within [-threshold, threshold] are classified as stable.
    """
    if dimension == "tension":
        if slope > threshold:
            return "deteriorating"
        elif slope < -threshold:
            return "improving"
        return "stable"
    else:
        if slope > threshold:
            return "improving"
        elif slope < -threshold:
            return "deteriorating"
        return "stable"
