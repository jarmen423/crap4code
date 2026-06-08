"""CLI integration tests."""

from __future__ import annotations

import contextlib
import io
import os
from pathlib import Path
import tempfile
import textwrap
import unittest

from unittest.mock import patch

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

    def test_unavailable_lang_returns_nonzero(self) -> None:
        """Explicit --lang for a missing grammar exits non-zero with guidance."""

        with patch("crap4code.cli.get_language_registry", return_value={"python": object()}):
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                code = main(["scan", "--lang", "rust"])

        self.assertEqual(code, 1)
        err_text = stderr.getvalue()
        self.assertIn("Rust support requires", err_text)
        self.assertIn("tree-sitter-rust", err_text)
        self.assertIn("These languages still work: python", err_text)

    def test_changed_flag_in_non_git_dir_emits_warning(self) -> None:
        """Exercise --changed (and --base-ref) when cwd is not a git repo.

        This is the primary regression / observability test for phase2-git-warn
        (Issue E2). A fresh TemporaryDirectory is guaranteed not to be inside a
        .git worktree, so `git diff ...` etc. will return non-zero (or OSError
        if git is not even on PATH). The implementation must:

        - not crash
        - return exit code 0 (same as "no files")
        - print the "No matching source files found." message
        - emit a clear "warning: git not available or not a repository..." line
          on stderr (the message may include a (git stderr: ...) snippet when
          git was present but the dir wasn't a repo)

        The warning must be visible even though we take the scanned_files==0
        early return (see the special handling added in cli.py).

        This scenario is exactly what Windows CI runners and temp-dir agent
        executions hit; before the change it was completely silent.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            old_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                stdout = io.StringIO()
                stderr = io.StringIO()
                with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                    code = main(["scan", "--changed", "--lang", "python"])
                # Also exercise the base_ref code path (still no repo).
                stdout2 = io.StringIO()
                stderr2 = io.StringIO()
                with contextlib.redirect_stdout(stdout2), contextlib.redirect_stderr(stderr2):
                    code2 = main(["scan", "--changed", "--base-ref", "origin/main", "--lang", "python"])
            finally:
                os.chdir(old_cwd)

        self.assertEqual(code, 0)
        self.assertIn("No matching source files found.", stdout.getvalue())
        err_text = stderr.getvalue()
        self.assertIn("warning: ", err_text)
        self.assertIn("git not available or not a repository", err_text)
        self.assertIn("--changed flag had no effect", err_text)

        # Same expectations for the base_ref variant.
        self.assertEqual(code2, 0)
        self.assertIn("No matching source files found.", stdout2.getvalue())
        err_text2 = stderr2.getvalue()
        self.assertIn("warning: ", err_text2)
        self.assertIn("git not available or not a repository", err_text2)


if __name__ == "__main__":
    unittest.main()
