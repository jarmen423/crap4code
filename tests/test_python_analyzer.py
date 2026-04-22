"""Python analyzer tests."""

from __future__ import annotations

from pathlib import Path
import tempfile
import textwrap
import unittest

from crap4code.languages.python.analyzer import PythonAnalyzer


class PythonAnalyzerTests(unittest.TestCase):
    """Check Python extraction and complexity behavior."""

    def test_extracts_functions_ranges_and_containers(self) -> None:
        source = textwrap.dedent(
            """
            class Example:
                def method(self, x):
                    if x > 2 and x < 10:
                        return x
                    return 0

            async def helper(flag):
                if flag:
                    return 1
                return 2
            """
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "sample.py"
            file_path.write_text(source, encoding="utf-8")
            rows = PythonAnalyzer().analyze(root=Path(tmpdir), files=[file_path])

        names = {row.function_name for row in rows}
        self.assertEqual(names, {"method", "helper"})

        method = next(row for row in rows if row.function_name == "method")
        helper = next(row for row in rows if row.function_name == "helper")

        self.assertEqual(method.container, "Example")
        self.assertGreaterEqual(method.complexity, 3)
        self.assertGreater(method.end_line, method.start_line)
        self.assertEqual(helper.container, "module")


if __name__ == "__main__":
    unittest.main()
