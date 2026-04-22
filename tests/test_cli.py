"""CLI integration tests."""

from __future__ import annotations

import contextlib
import io
import os
from pathlib import Path
import tempfile
import textwrap
import unittest

from crap4code.cli import main


class CliTests(unittest.TestCase):
    """Validate user-visible CLI behavior."""

    def test_init_writes_sample_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            old_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    code = main(["init"])
            finally:
                os.chdir(old_cwd)

            self.assertEqual(code, 0)
            self.assertTrue((Path(tmpdir) / ".crap4code.toml").exists())
            self.assertIn("Wrote sample config", output.getvalue())

    def test_scan_json_threshold_breach_returns_2(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "src").mkdir()
            (root / "src" / "sample.py").write_text(
                textwrap.dedent(
                    """
                    def risky(flag):
                        if flag:
                            return 1
                        return 0
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (root / "coverage.xml").write_text(
                textwrap.dedent(
                    """\
                    <?xml version="1.0" ?>
                    <coverage>
                      <packages>
                        <package name="src">
                          <classes>
                            <class name="sample" filename="src/sample.py">
                              <lines>
                                <line number="1" hits="1"/>
                                <line number="2" hits="0"/>
                                <line number="3" hits="0"/>
                                <line number="4" hits="1"/>
                              </lines>
                            </class>
                          </classes>
                        </package>
                      </packages>
                    </coverage>
                    """
                ),
                encoding="utf-8",
            )
            (root / ".crap4code.toml").write_text(
                textwrap.dedent(
                    """
                    [scan]
                    default_paths = ["src"]
                    threshold = 1.0
                    format = "json"

                    [python]
                    enabled = true
                    paths = ["src"]
                    coverage_report = "coverage.xml"
                    coverage_format = "coverage.py-xml"

                    [javascript]
                    enabled = false

                    [typescript]
                    enabled = false

                    [rust]
                    enabled = false
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            old_cwd = os.getcwd()
            try:
                os.chdir(root)
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    code = main(["scan"])
            finally:
                os.chdir(old_cwd)

        self.assertEqual(code, 2)
        self.assertIn('"threshold_exceeded": true', output.getvalue())
        self.assertIn('"coverage_state": "measured"', output.getvalue())

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


if __name__ == "__main__":
    unittest.main()
