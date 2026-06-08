#!/usr/bin/env python3
"""verify_minimal_install.py

Standalone verification script for the "minimal-install-verify" CI job.

Extracted from the problematic inline Python heredoc (python - << 'PYEOF' ...)
that lived inside .github/workflows/ci.yml 's "Verify python scan works..."
step. The heredoc caused YAML parse errors ("while scanning a simple key",
"could not find expected ':'") due to indentation mismatch between the
YAML block scalar (run: |) and the unindented heredoc payload lines.

This script performs *exactly* the same checks the original inline code did:

1. Under the simulated minimal/python-only state (after full [dev] install
   followed by `pip uninstall -y` of the JS/TS/Rust grammars), import the
   registry and assert it contains exactly ["python"].
2. Invoke `main(["scan", "--lang", "rust"])` and assert:
   - it returns exit code 1 (graceful failure, no crash/traceback)
   - the captured stderr contains the expected messages:
     "Rust support requires" and "tree-sitter-rust"
3. Create a temporary project containing:
   - a sample.py with a "foo" function (to have identifiable output)
   - a .crap4code.toml that forces python enabled + paths so scan actually
     processes files (without it, defaults can lead to "No matching source
     files found" even if .py is present)
   chdir into that tempdir (with proper save/restore + finally), run
   `main(["scan", "--lang", "python", "--report-only"])`, and assert:
   - return code is 0 or 2 (success or "issues found but ran")
   - the string "foo" appears in the captured stdout (proving the function
     was analyzed and reported)
4. Print the same success marker lines the original printed, for easy
   visibility in CI logs:
   - REGISTRY_OK
   - GRACEFUL_RUST_OK
   - PYTHON_SCAN_OK_UNDER_MINIMAL
   - MINIMAL_VERIFY_COMPLETE

Usage in CI (after the "Install project (full)" + "Simulate minimal/..."
steps):
    python scripts/verify_minimal_install.py

Can also be run directly (if made executable):
    chmod +x scripts/verify_minimal_install.py
    ./scripts/verify_minimal_install.py

It is intentionally *not* a pytest test (the job already has a later
targeted pytest step). It is a self-contained smoke that exercises the
real CLI entrypoint + lazy registry behavior under missing optional
grammars. This matches the manual verification commands listed in
docs/release-checklist.md under "Cross-Platform / Windows Verification
(phase3-ci / Dev4)".

Robustness notes:
- Uses tempfile.TemporaryDirectory (auto cleanup even on exceptions).
- Saves/restores os.getcwd() with try/finally around chdir (defensive;
  the redirect context does not affect cwd).
- Captures I/O with contextlib.redirect_stdout / redirect_stderr + StringIO.
- No external test deps beyond stdlib + the installed crap4code package.
- Top-level imports happen before any chdir, so package is found via the
  editable install regardless of later cwd changes.
- Assertions will cause non-zero exit (and CI step failure) on any
  mismatch, preserving the original "fail fast on bad minimal state" intent.

See:
- .github/workflows/ci.yml (the minimal-install-verify job and its comments)
- docs/release-checklist.md (the manual steps this CI job automates)
- src/crap4code/languages/registry.py and cli.py (the lazy loading + graceful
  error paths being exercised)
- CHANGELOG.md (mentions of the minimal-install-verify job)

This file was introduced as part of fixing the phase3-ci YAML heredoc
syntax error while keeping the verification logic identical and auditable.
"""

import contextlib
import io
import os
import sys
import tempfile
from pathlib import Path

# These imports must succeed even in a "minimal" install because:
# - python analyzer is pure stdlib (ast), no tree-sitter dep
# - the registry itself tolerates missing optional grammars (lazy)
from crap4code.cli import main
from crap4code.languages import get_language_registry


def main_verify() -> None:
    """Run the exact minimal-install verification sequence.

    Exits non-zero (via assert or explicit) on any failure so that the
    calling CI step fails. Prints progress + the original marker strings.
    """
    print("=== REGISTRY UNDER MINIMAL ===")
    langs = sorted(get_language_registry().keys())
    print(langs)
    assert langs == ["python"], f"Expected only python in registry under minimal, got: {langs}"
    print("REGISTRY_OK")

    print("=== GRACEFUL --lang rust FAIL (real missing, no traceback) ===")
    stderr = io.StringIO()
    with contextlib.redirect_stderr(stderr):
        code = main(["scan", "--lang", "rust"])
    err = stderr.getvalue()
    print("code:", code)
    print("msg excerpt:", err[:200] if err else "(no stderr)")
    assert code == 1, f"Expected exit code 1 for unavailable rust, got {code}"
    assert "Rust support requires" in err, f"Missing 'Rust support requires' in stderr: {err[:300]}"
    assert "tree-sitter-rust" in err, f"Missing 'tree-sitter-rust' in stderr: {err[:300]}"
    print("GRACEFUL_RUST_OK")

    print("=== FULL PYTHON SCAN WORKS (actual .py file + config, lazy path) ===")
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "sample.py").write_text(
            "def foo(flag):\n    if flag:\n        return 1\n    return 0\n",
            encoding="utf-8",
        )
        # minimal config to enable python paths so scan actually processes the file
        # (without it, defaults may yield 'No matching source files found' even if .py present)
        (root / ".crap4code.toml").write_text(
            "[scan]\ndefault_paths = [\".\"]\n\n[python]\nenabled = true\npaths = [\".\"]\n",
            encoding="utf-8",
        )
        old = os.getcwd()
        os.chdir(root)
        try:
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                c2 = main(["scan", "--lang", "python", "--report-only"])
            outv = out.getvalue()
            print("scan_code:", c2)
            print("scan_has_foo:", "foo" in outv)
            assert c2 in (0, 2), f"Expected scan exit 0 or 2, got {c2}"
            assert "foo" in outv, f"'foo' not found in scan output under minimal:\n{outv[:500]}"
        finally:
            os.chdir(old)
    print("PYTHON_SCAN_OK_UNDER_MINIMAL")
    print("MINIMAL_VERIFY_COMPLETE")


if __name__ == "__main__":
    # When invoked as `python scripts/verify_minimal_install.py` (the way CI calls it)
    # or directly if +x.
    # We keep it simple: run the verify at import time under __main__ guard.
    # No argparse needed; this is a fixed CI smoke, not a general tool.
    try:
        main_verify()
    except AssertionError as exc:
        print("MINIMAL_VERIFY_FAILED:", exc, file=sys.stderr)
        sys.exit(1)
    except Exception as exc:  # pragma: no cover - defensive for CI visibility
        print("MINIMAL_VERIFY_UNEXPECTED_ERROR:", repr(exc), file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(2)
