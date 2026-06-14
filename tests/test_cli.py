"""CLI integration tests."""

from __future__ import annotations

import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import textwrap
import unittest

from unittest.mock import patch

from crap4code.cli import main


REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES_PYTHON = REPO_ROOT / "tests" / "fixtures" / "python"
SAMPLE_ROOT = Path(__file__).parent / "sample_projects"


def _write_minimal_python_project(
    root: Path,
    *,
    source_files: dict[str, str] | None = None,
    coverage_xml: str | None = None,
    lcov_path: str | None = None,
    lcov_content: str | None = None,
    threshold: float = 8.0,
    coverage_report: str = "coverage.xml",
    coverage_format: str = "coverage.py-xml",
    coverage_command: str | None = "python -m coverage run -m pytest",
) -> None:
    """Scaffold a tiny python-only project for targeted CLI tests."""

    src = root / "src"
    src.mkdir(parents=True, exist_ok=True)
    files = source_files or {
        "src/mod.py": (
            "def alpha():\n"
            "    if True:\n"
            "        return 1\n"
            "    return 0\n\n"
            "def beta():\n"
            "    return 2\n"
        ),
    }
    for rel, body in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")

    if coverage_xml is not None:
        (root / "coverage.xml").write_text(coverage_xml, encoding="utf-8")
    if lcov_content is not None and lcov_path is not None:
        lcov_file = root / lcov_path
        lcov_file.parent.mkdir(parents=True, exist_ok=True)
        lcov_file.write_text(lcov_content, encoding="utf-8")

    cmd_line = f'coverage_command = "{coverage_command}"' if coverage_command else ""
    (root / ".crap4code.toml").write_text(
        textwrap.dedent(
            f"""
            [scan]
            default_paths = ["src"]
            threshold = {threshold}
            format = "json"

            [python]
            enabled = true
            paths = ["src"]
            coverage_report = "{coverage_report}"
            coverage_format = "{coverage_format}"
            {cmd_line}

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


_DEFAULT_COVERAGE_XML = textwrap.dedent(
    """\
    <?xml version="1.0" ?>
    <coverage>
      <packages>
        <package name="src">
          <classes>
            <class name="mod" filename="src/mod.py">
              <lines>
                <line number="1" hits="1"/>
                <line number="2" hits="1"/>
                <line number="3" hits="0"/>
                <line number="4" hits="1"/>
                <line number="5" hits="1"/>
                <line number="7" hits="1"/>
                <line number="8" hits="1"/>
              </lines>
            </class>
          </classes>
        </package>
      </packages>
    </coverage>
    """
)


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


class TargetedRemediationCliTests(unittest.TestCase):
    """CLI tests for --function, coverage overrides, and --format compact."""

    def _run_in(self, root: Path, argv: list[str]) -> tuple[int, str, str]:
        old_cwd = os.getcwd()
        try:
            os.chdir(root)
            stdout = io.StringIO()
            stderr = io.StringIO()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                code = main(argv)
            return code, stdout.getvalue(), stderr.getvalue()
        finally:
            os.chdir(old_cwd)

    def test_function_single_match(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write_minimal_python_project(root, coverage_xml=_DEFAULT_COVERAGE_XML)
            code, out, _ = self._run_in(
                root,
                ["scan", "--report-only", "--function", "alpha", "--format", "json", "--lang", "python"],
            )
            self.assertEqual(code, 0)
            payload = json.loads(out)
            self.assertEqual(payload["summary"]["functions_found"], 1)
            self.assertEqual(payload["functions"][0]["function_name"], "alpha")

    def test_function_repeated_flags(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write_minimal_python_project(root, coverage_xml=_DEFAULT_COVERAGE_XML)
            code, out, _ = self._run_in(
                root,
                [
                    "scan",
                    "--report-only",
                    "--function",
                    "alpha",
                    "--function",
                    "beta",
                    "--format",
                    "json",
                    "--lang",
                    "python",
                ],
            )
            self.assertEqual(code, 0)
            names = {row["function_name"] for row in json.loads(out)["functions"]}
            self.assertEqual(names, {"alpha", "beta"})

    def test_function_duplicate_names_two_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write_minimal_python_project(
                root,
                source_files={
                    "src/a.py": "def helper():\n    if True:\n        pass\n",
                    "src/b.py": "def helper():\n    return 1\n",
                },
                coverage_xml=textwrap.dedent(
                    """\
                    <?xml version="1.0" ?>
                    <coverage>
                      <packages>
                        <package name="src">
                          <classes>
                            <class name="a" filename="src/a.py">
                              <lines>
                                <line number="1" hits="1"/>
                                <line number="2" hits="1"/>
                                <line number="3" hits="1"/>
                              </lines>
                            </class>
                            <class name="b" filename="src/b.py">
                              <lines>
                                <line number="1" hits="1"/>
                                <line number="2" hits="1"/>
                              </lines>
                            </class>
                          </classes>
                        </package>
                      </packages>
                    </coverage>
                    """
                ),
            )
            code, out, _ = self._run_in(
                root,
                ["scan", "--report-only", "--function", "helper", "--format", "json", "--lang", "python"],
            )
            self.assertEqual(code, 0)
            rows = json.loads(out)["functions"]
            self.assertEqual(len(rows), 2)
            paths = {row["file_path"] for row in rows}
            self.assertEqual(paths, {"src/a.py", "src/b.py"})

    def test_function_no_match_exit_1(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write_minimal_python_project(root, coverage_xml=_DEFAULT_COVERAGE_XML)
            code, _, err = self._run_in(
                root,
                ["scan", "--report-only", "--function", "missing_fn", "--lang", "python"],
            )
            self.assertEqual(code, 1)
            self.assertIn("No functions matched --function", err)
            self.assertIn("disambiguate", err)

    def test_coverage_report_relative_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            lcov = textwrap.dedent(
                """\
                TN:
                SF:src/mod.py
                DA:1,1
                DA:2,1
                DA:3,0
                DA:4,1
                DA:5,1
                DA:7,1
                DA:8,1
                end_of_record
                """
            )
            _write_minimal_python_project(
                root,
                coverage_xml=None,
                lcov_path="reports/target.lcov",
                lcov_content=lcov,
                coverage_report="reports/target.lcov",
                coverage_format="lcov",
            )
            code, out, _ = self._run_in(
                root,
                [
                    "scan",
                    "--report-only",
                    "--coverage-report",
                    "reports/target.lcov",
                    "--coverage-format",
                    "lcov",
                    "--function",
                    "alpha",
                    "--lang",
                    "python",
                ],
            )
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(out)["functions"][0]["coverage_state"], "measured")

    def test_coverage_report_absolute_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            abs_lcov = Path(tmpdir) / "abs.lcov"
            abs_lcov.write_text(
                textwrap.dedent(
                    """\
                    TN:
                    SF:src/mod.py
                    DA:1,1
                    DA:2,1
                    DA:3,0
                    DA:4,1
                    DA:5,1
                    DA:7,1
                    DA:8,1
                    end_of_record
                    """
                ),
                encoding="utf-8",
            )
            _write_minimal_python_project(
                root,
                coverage_xml=None,
                coverage_report="coverage.xml",
                coverage_format="coverage.py-xml",
            )
            code, out, _ = self._run_in(
                root,
                [
                    "scan",
                    "--report-only",
                    "--coverage-report",
                    str(abs_lcov),
                    "--coverage-format",
                    "lcov",
                    "--function",
                    "alpha",
                    "--lang",
                    "python",
                ],
            )
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(out)["functions"][0]["coverage_state"], "measured")

    def test_coverage_format_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            lcov = textwrap.dedent(
                """\
                TN:
                SF:src/mod.py
                DA:1,1
                DA:2,1
                DA:3,0
                DA:4,1
                DA:5,1
                DA:7,1
                DA:8,1
                end_of_record
                """
            )
            _write_minimal_python_project(
                root,
                coverage_xml=None,
                lcov_path="out.lcov",
                lcov_content=lcov,
                coverage_report="out.lcov",
                coverage_format="lcov",
            )
            code, out, _ = self._run_in(
                root,
                [
                    "scan",
                    "--report-only",
                    "--coverage-report",
                    "out.lcov",
                    "--coverage-format",
                    "lcov",
                    "--lang",
                    "python",
                ],
            )
            self.assertEqual(code, 0)
            self.assertTrue(all(r["coverage_state"] == "measured" for r in json.loads(out)["functions"]))

    def test_coverage_report_missing_explicit_exit_1(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write_minimal_python_project(root, coverage_xml=_DEFAULT_COVERAGE_XML)
            code, out, err = self._run_in(
                root,
                [
                    "scan",
                    "--report-only",
                    "--coverage-report",
                    "/tmp/does-not-exist.lcov",
                    "--coverage-format",
                    "lcov",
                    "--lang",
                    "python",
                ],
            )
            self.assertEqual(code, 1)
            self.assertIn("Coverage report not found", err)
            self.assertEqual(out, "")

    def test_coverage_format_mismatch_exit_1(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write_minimal_python_project(root, coverage_xml=_DEFAULT_COVERAGE_XML)
            code, _, err = self._run_in(
                root,
                [
                    "scan",
                    "--report-only",
                    "--coverage-report",
                    "coverage.xml",
                    "--coverage-format",
                    "lcov",
                    "--lang",
                    "python",
                ],
            )
            self.assertEqual(code, 1)
            self.assertIn("does not look like LCOV", err)

    def test_compact_measured_line(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write_minimal_python_project(root, coverage_xml=_DEFAULT_COVERAGE_XML)
            code, out, err = self._run_in(
                root,
                [
                    "scan",
                    "--report-only",
                    "--function",
                    "alpha",
                    "--format",
                    "compact",
                    "--lang",
                    "python",
                ],
            )
            self.assertEqual(code, 0)
            self.assertNotIn("\x1b", out)
            self.assertIn("src/mod.py::alpha", out)
            self.assertIn("lines=", out)
            self.assertIn("CX=", out)
            self.assertIn("coverage=", out)
            self.assertIn("CRAP=", out)
            self.assertIn("risk=", out)
            self.assertNotIn("scanned_files=", out)
            self.assertEqual(out.strip().count("\n"), 0)
            self.assertNotIn("warning:", err)  # warnings on stderr only

    def test_compact_indeterminate_line(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write_minimal_python_project(root, coverage_xml=None, coverage_command=None)
            (root / ".crap4code.toml").write_text(
                (root / ".crap4code.toml").read_text(encoding="utf-8").replace(
                    'coverage_report = "coverage.xml"',
                    'coverage_report = "missing.xml"',
                ),
                encoding="utf-8",
            )
            code, out, _ = self._run_in(
                root,
                ["scan", "--report-only", "--function", "alpha", "--format", "compact", "--lang", "python"],
            )
            self.assertEqual(code, 0)
            self.assertIn("coverage=N/A", out)
            self.assertIn("CRAP=N/A", out)

    def test_threshold_only_selected_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write_minimal_python_project(
                root,
                source_files={
                    "src/mod.py": (
                        "def risky():\n"
                        "    if True:\n"
                        "        if False:\n"
                        "            pass\n"
                        "    return 0\n\n"
                        "def safe():\n"
                        "    return 1\n"
                    ),
                },
                coverage_xml=textwrap.dedent(
                    """\
                    <?xml version="1.0" ?>
                    <coverage>
                      <packages>
                        <package name="src">
                          <classes>
                            <class name="mod" filename="src/mod.py">
                              <lines>
                                <line number="1" hits="1"/>
                                <line number="2" hits="1"/>
                                <line number="3" hits="0"/>
                                <line number="4" hits="0"/>
                                <line number="5" hits="0"/>
                                <line number="6" hits="1"/>
                                <line number="8" hits="1"/>
                                <line number="9" hits="1"/>
                              </lines>
                            </class>
                          </classes>
                        </package>
                      </packages>
                    </coverage>
                    """
                ),
                threshold=1.0,
            )
            code_ok, _, _ = self._run_in(
                root,
                [
                    "scan",
                    "--report-only",
                    "--function",
                    "safe",
                    "--threshold",
                    "8",
                    "--lang",
                    "python",
                ],
            )
            self.assertEqual(code_ok, 0)

            code_breach, _, _ = self._run_in(
                root,
                [
                    "scan",
                    "--report-only",
                    "--function",
                    "risky",
                    "--threshold",
                    "1",
                    "--lang",
                    "python",
                ],
            )
            self.assertEqual(code_breach, 2)

    def test_json_summary_after_function_filter(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write_minimal_python_project(root, coverage_xml=_DEFAULT_COVERAGE_XML)
            code, out, _ = self._run_in(
                root,
                ["scan", "--report-only", "--function", "beta", "--format", "json", "--lang", "python"],
            )
            self.assertEqual(code, 0)
            summary = json.loads(out)["summary"]
            self.assertEqual(summary["functions_found"], 1)
            self.assertEqual(summary["by_language"], {"python": 1})

    def test_report_only_skips_coverage_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write_minimal_python_project(root, coverage_xml=_DEFAULT_COVERAGE_XML)
            with patch("crap4code.cli.run_coverage_command") as mocked:
                code, _, _ = self._run_in(
                    root,
                    [
                        "scan",
                        "--report-only",
                        "--coverage-report",
                        "coverage.xml",
                        "--coverage-format",
                        "coverage.py-xml",
                        "--lang",
                        "python",
                    ],
                )
            self.assertEqual(code, 0)
            mocked.assert_not_called()

    def test_limit_negative_rejected(self) -> None:
        code = main(["scan", "--limit", "-1", "--lang", "python"])
        self.assertEqual(code, 1)

    def test_python_fixture_with_coverage_override(self) -> None:
        old_cwd = os.getcwd()
        try:
            os.chdir(REPO_ROOT)
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = main(
                    [
                        "scan",
                        str(FIXTURES_PYTHON / "sample.py"),
                        "--lang",
                        "python",
                        "--report-only",
                        "--coverage-report",
                        "tests/fixtures/python/coverage.xml",
                        "--coverage-format",
                        "coverage.py-xml",
                        "--function",
                        "helper",
                        "--format",
                        "compact",
                    ]
                )
        finally:
            os.chdir(old_cwd)
        self.assertEqual(code, 0)
        out = stdout.getvalue()
        self.assertIn("tests/fixtures/python/sample.py::helper", out)
        self.assertIn("coverage=", out)

    def test_rust_targeted_compact_smoke(self) -> None:
        project_root = SAMPLE_ROOT / "rust_repo"
        old_cwd = os.getcwd()
        try:
            os.chdir(project_root)
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = main(
                    [
                        "scan",
                        "src/sample.rs",
                        "--lang",
                        "rust",
                        "--report-only",
                        "--coverage-report",
                        "coverage/lcov.info",
                        "--coverage-format",
                        "lcov",
                        "--function",
                        "free_run",
                        "--format",
                        "compact",
                    ]
                )
        finally:
            os.chdir(old_cwd)
        self.assertEqual(code, 0)
        self.assertIn("src/sample.rs::free_run", stdout.getvalue())

    def test_output_html_inference_and_structure(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write_minimal_python_project(root, coverage_xml=_DEFAULT_COVERAGE_XML)
            out_file = root / "report.html"
            code, _, _ = self._run_in(
                root,
                ["scan", "--report-only", "--output", str(out_file), "--lang", "python"],
            )
            self.assertEqual(code, 0)
            html = out_file.read_text(encoding="utf-8")
            self.assertIn("<!DOCTYPE html>", html)
            self.assertIn("crap4code", html)

    def test_limit_truncation_message_in_plain_table(self) -> None:
        """--limit applies to rich table; file output uses plain format_report (all rows)."""

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write_minimal_python_project(root, coverage_xml=_DEFAULT_COVERAGE_XML)
            out_file = root / "table.txt"
            code, _, _ = self._run_in(
                root,
                [
                    "scan",
                    "--report-only",
                    "--output",
                    str(out_file),
                    "--limit",
                    "1",
                    "--lang",
                    "python",
                ],
            )
            self.assertEqual(code, 0)
            text = out_file.read_text(encoding="utf-8")
            self.assertIn("alpha", text)
            self.assertIn("beta", text)


if __name__ == "__main__":
    unittest.main()
