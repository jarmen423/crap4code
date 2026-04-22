"""Threshold helpers."""

from __future__ import annotations

from collections.abc import Iterable

from crap4code.core.models import FunctionMetrics


DEFAULT_THRESHOLD = 8.0


def is_threshold_exceeded(
    metrics: Iterable[FunctionMetrics],
    threshold: float = DEFAULT_THRESHOLD,
) -> bool:
    """Return ``True`` when any measured CRAP score breaches the threshold."""

    return any(row.crap_score is not None and row.crap_score > threshold for row in metrics)
