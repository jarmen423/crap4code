import unittest

from crap4code.core.models import FunctionMetrics
from crap4code.core.thresholds import is_threshold_exceeded


class ThresholdTests(unittest.TestCase):
    def test_threshold_exceeded(self) -> None:
        rows = [
            FunctionMetrics("python", "a.py", "module", "f", 1, 2, None, 4.0),
            FunctionMetrics("python", "b.py", "module", "g", 1, 9, None, 12.0),
        ]
        self.assertTrue(is_threshold_exceeded(rows, threshold=8.0))

    def test_threshold_not_exceeded(self) -> None:
        rows = [FunctionMetrics("python", "a.py", "module", "f", 1, 2, None, 4.0)]
        self.assertFalse(is_threshold_exceeded(rows, threshold=8.0))


if __name__ == "__main__":
    unittest.main()
