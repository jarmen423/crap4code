import contextlib
import io
import os
import tempfile
import unittest
from pathlib import Path

from crap4code.cli import main


class CliTests(unittest.TestCase):
    def test_invalid_usage_returns_1(self) -> None:
        code = main(["scan", "--lang", "invalid"])
        self.assertEqual(code, 1)

    def test_no_files_found_returns_0(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            old_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    code = main(["scan", "--lang", "python"])
            finally:
                os.chdir(old_cwd)

        self.assertEqual(code, 0)
        self.assertIn("No matching source files found.", output.getvalue())

    def test_scan_explicit_file_prints_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            old_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                test_file = Path(tmpdir) / "sample.py"
                test_file.write_text("def hello():\n    return 1\n", encoding="utf-8")
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    code = main(["scan", "--lang", "python", str(test_file)])
            finally:
                os.chdir(old_cwd)

        self.assertEqual(code, 0)
        self.assertIn("hello", output.getvalue())


if __name__ == "__main__":
    unittest.main()
