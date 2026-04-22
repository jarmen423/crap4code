"""End-to-end tests against checked-in sample repos."""

from __future__ import annotations

import contextlib
import io
import json
import os
from pathlib import Path
import unittest

from crap4code.cli import main


SAMPLE_ROOT = Path(__file__).parent / "sample_projects"


class SampleProjectTests(unittest.TestCase):
    """Verify release-readiness scenarios against checked-in sample repos."""

    def _run_scan(self, sample_name: str, *args: str) -> tuple[int, dict[str, object]]:
        project_root = SAMPLE_ROOT / sample_name
        old_cwd = os.getcwd()
        try:
            os.chdir(project_root)
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = main(["scan", "--report-only", *args])
        finally:
            os.chdir(old_cwd)

        return (code, json.loads(output.getvalue()))

    def test_python_sample_repo(self) -> None:
        code, payload = self._run_scan("python_repo")
        self.assertEqual(code, 2)
        self.assertEqual(payload["summary"]["by_language"], {"python": 1})
        self.assertEqual(payload["functions"][0]["coverage_state"], "measured")

    def test_javascript_sample_repo(self) -> None:
        code, payload = self._run_scan("javascript_repo")
        self.assertEqual(code, 0)
        self.assertEqual(payload["summary"]["by_language"], {"javascript": 2})
        self.assertTrue(all(row["coverage_state"] == "measured" for row in payload["functions"]))

    def test_rust_sample_repo(self) -> None:
        code, payload = self._run_scan("rust_repo")
        self.assertEqual(code, 0)
        self.assertEqual(payload["summary"]["by_language"], {"rust": 2})
        containers = {row["function_name"]: row["container"] for row in payload["functions"]}
        self.assertEqual(containers["work"], "Service (impl Worker)")

    def test_mixed_sample_repo(self) -> None:
        code, payload = self._run_scan("mixed_repo")
        self.assertEqual(code, 0)
        self.assertEqual(
            payload["summary"]["by_language"],
            {"javascript": 1, "python": 1, "rust": 1},
        )


if __name__ == "__main__":
    unittest.main()
