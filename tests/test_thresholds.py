"""Threshold tests."""

from __future__ import annotations

import unittest

from crap4code.core.models import FunctionMetrics
from crap4code.core.thresholds import is_threshold_exceeded


class ThresholdTests(unittest.TestCase):
    """Validate threshold evaluation."""

    def test_threshold_exceeded(self) -> None:
        rows = [
            FunctionMetrics("python", "a.py", "module", "f", 1, 2, 2, crap_score=4.0),
            FunctionMetrics("python", "b.py", "module", "g", 1, 4, 9, crap_score=12.0),
        ]
        self.assertTrue(is_threshold_exceeded(rows, threshold=8.0))

    def test_threshold_not_exceeded(self) -> None:
        rows = [FunctionMetrics("python", "a.py", "module", "f", 1, 2, 2, crap_score=4.0)]
        self.assertFalse(is_threshold_exceeded(rows, threshold=8.0))


if __name__ == "__main__":
    unittest.main()
