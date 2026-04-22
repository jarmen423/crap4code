"""CRAP formula tests."""

from __future__ import annotations

import unittest

from crap4code.core.crap_score import calculate_crap


class CrapScoreTests(unittest.TestCase):
    """Validate the core CRAP formula."""

    def test_zero_coverage(self) -> None:
        self.assertEqual(calculate_crap(2, 0.0), 6.0)

    def test_full_coverage(self) -> None:
        self.assertEqual(calculate_crap(4, 1.0), 4.0)

    def test_missing_coverage(self) -> None:
        self.assertIsNone(calculate_crap(3, None))


if __name__ == "__main__":
    unittest.main()
