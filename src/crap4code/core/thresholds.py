from collections.abc import Iterable

from .models import FunctionMetrics

DEFAULT_THRESHOLD = 8.0


def is_threshold_exceeded(
    metrics: Iterable[FunctionMetrics], threshold: float = DEFAULT_THRESHOLD
) -> bool:
    return any(
        row.crap_score is not None and row.crap_score > threshold for row in metrics
    )
