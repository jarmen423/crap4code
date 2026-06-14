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

    def test_baseline_filters_to_previous_functions_and_attaches_snapshots(self) -> None:
        """Exercise --baseline end-to-end on the CLI.

        - Creates a tiny hermetic python project (single .py with two functions).
        - Runs a --report-only scan (no coverage needed; we only care about
          function discovery + the filtering/delta attachment contract).
        - Builds a synthetic baseline JSON containing only *one* of the two
          functions (simulating "the parts that were risky in the prior full scan").
        - Re-runs the scan with --baseline pointing at that file.
        - Asserts:
          * functions_found in the JSON is 1 (filtered)
          * the single function carries baseline_crap_score / baseline_coverage_percent
            matching what we put in the synthetic baseline
          * baseline_path and baseline_matched appear in summary
          * A bad --baseline path produces a warning but still succeeds (unfiltered
            for the scope, i.e. both functions in this case).
        This directly covers the "just scan the parts you worked on vs that baseline"
        user workflow without relying on sample projects or real coverage artifacts.
        """
        import json as _json  # local to avoid shadowing

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            src = root / "src"
            src.mkdir()
            py = src / "mod.py"
            py.write_text(
                "def foo():\n    if True:\n        pass\n\ndef bar():\n    return 1\n",
                encoding="utf-8",
            )

            # First: a normal (unfiltered) run to see both functions exist.
            stdout_full = io.StringIO()
            stderr_full = io.StringIO()
            with contextlib.redirect_stdout(stdout_full), contextlib.redirect_stderr(stderr_full):
                code_full = main(["scan", str(py), "--report-only", "--format", "json", "--lang", "python"])
            self.assertEqual(code_full, 0)
            full_report = _json.loads(stdout_full.getvalue())
            self.assertEqual(full_report["summary"]["functions_found"], 2)

            # Pick the first function that the real analyzer produced for this tiny tree
            # so the synthetic baseline key will definitely match (avoids any
            # repo-relative path surprises between discovery and the test's baseline).
            real_first = full_report["functions"][0]
            baseline_path = root / "baseline.json"
            baseline = {
                "summary": {"functions_found": 1},
                "functions": [
                    {
                        "file_path": real_first["file_path"],
                        "container": real_first.get("container", "module"),
                        "function_name": real_first["function_name"],
                        "crap_score": 12.34,
                        "coverage_percent": 55.5,
                    }
                ],
            }
            baseline_path.write_text(_json.dumps(baseline), encoding="utf-8")

            # Focused run with --baseline.
            stdout_f = io.StringIO()
            stderr_f = io.StringIO()
            with contextlib.redirect_stdout(stdout_f), contextlib.redirect_stderr(stderr_f):
                code_f = main(
                    [
                        "scan",
                        str(py),
                        "--report-only",
                        "--format",
                        "json",
                        "--lang",
                        "python",
                        "--baseline",
                        str(baseline_path),
                    ]
                )
            self.assertEqual(code_f, 0)
            focused = _json.loads(stdout_f.getvalue())
            self.assertEqual(focused["summary"]["functions_found"], 1)
            self.assertEqual(focused["summary"]["baseline_matched"], 1)
            self.assertEqual(focused["summary"]["baseline_path"], str(baseline_path))
            fn = focused["functions"][0]
            self.assertEqual(fn["function_name"], "foo")
            self.assertAlmostEqual(fn.get("baseline_crap_score"), 12.34)
            self.assertAlmostEqual(fn.get("baseline_coverage_percent"), 55.5)

            # Bad baseline path: warning emitted, scan still succeeds with the
            # unfiltered scope for the supplied paths (both functions).
            bad_baseline = root / "does-not-exist.json"
            stdout_bad = io.StringIO()
            stderr_bad = io.StringIO()
            with contextlib.redirect_stdout(stdout_bad), contextlib.redirect_stderr(stderr_bad):
                code_bad = main(
                    [
                        "scan",
                        str(py),
                        "--report-only",
                        "--format",
                        "json",
                        "--lang",
                        "python",
                        "--baseline",
                        str(bad_baseline),
                    ]
                )
            self.assertEqual(code_bad, 0)
            bad_report = _json.loads(stdout_bad.getvalue())
            self.assertEqual(bad_report["summary"]["functions_found"], 2)  # not filtered
            err_bad = stderr_bad.getvalue()
            self.assertIn("warning:", err_bad)
            self.assertIn("Failed to load --baseline", err_bad)


if __name__ == "__main__":
    unittest.main()
