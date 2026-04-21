import tempfile
import textwrap
import unittest
from pathlib import Path

from crap4code.analyzers.python import PythonAnalyzer


class PythonAnalyzerTests(unittest.TestCase):
    def test_extracts_functions_and_complexity(self) -> None:
        source = textwrap.dedent(
            """
            class Example:
                def method(self, x):
                    if x > 2 and x < 10:
                        return x
                    return 0

            def helper(flag):
                if flag:
                    return 1
                return 2
            """
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "sample.py"
            file_path.write_text(source, encoding="utf-8")

            analyzer = PythonAnalyzer()
            rows = analyzer.analyze([file_path])

        names = {row.function_name for row in rows}
        self.assertEqual(names, {"method", "helper"})

        complexity = {row.function_name: row.complexity for row in rows}
        self.assertGreaterEqual(complexity["method"], 3)
        self.assertGreaterEqual(complexity["helper"], 2)


if __name__ == "__main__":
    unittest.main()
