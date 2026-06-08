"""tests/conftest.py

Pytest configuration and cross-platform import guard for the crap4code test suite.

This module exists primarily to solve **Issue Dev1** (pytest PYTHONPATH friction
on Windows pwsh / cmd / bash) from the WINDOWS_AND_CROSS_PLATFORM_PLAN.md.

### Why this guard exists (root cause)
- The project uses a src/ layout (`src/crap4code/...`).
- `pyproject.toml` declares `[tool.pytest.ini_options] pythonpath = ["src"]` and
  `testpaths = ["tests"]`. This tells pytest to inject the src dir onto sys.path
  during collection and test execution.
- After `python -m pip install -e .[dev]`, the editable install (via setuptools)
  normally makes `import crap4code` succeed for *any* python invocation because
  it creates a .pth file (or uses an import hook) in site-packages that points
  back to the src/ tree.
- However, in practice on Windows this combination is fragile:
  - Different shells (pwsh, cmd.exe, Git Bash) have different syntax and timing
    for environment variables. Users often had to do `$env:PYTHONPATH='src'`
    (pwsh), `set PYTHONPATH=src` (cmd), or `PYTHONPATH=src ...` (bash) even when
    the pyproject config was present.
  - Editable installs can land in user-site vs venv; PATH/ComSpec differences,
    VS Code terminals, or "python" launcher vs direct python.exe can cause the
    .pth not to be honored at the exact moment `python -m pytest` runs.
  - Early in the project's life, tree-sitter native imports amplified the pain:
    a failed top-level import during collection produced confusing errors before
    any test code ran. (The lazy registry work in Phase 1 reduced blast radius
    for missing grammars, but the import-of-the-package-during-pytest-collection
    problem remained for the DX of running the suite itself.)
- The result: contributors on Windows could not simply follow "pip install -e .[dev]
  && python -m pytest -q" and have it "just work" across shells without manual
  env var twiddling.

### The chosen fix (minimal, robust, no new runtime deps)
- We keep `pythonpath = ["src"]` in pyproject.toml (it still helps pytest's own
  collection machinery and is harmless).
- We add this stdlib-only guard **in tests/conftest.py**.
- The guard does:
    try:
        import crap4code
    except ImportError:
        # only then: prepend the sibling src/ to sys.path
- This runs at conftest import time (pytest loads directory conftests before
  importing the test_*.py modules that contain the real `from crap4code...`
  statements).
- Because it only acts on ImportError, an already-successful editable install
  (or the pytest pythonpath injection, or a manual PYTHONPATH) wins and we
  never pollute sys.path unnecessarily.
- It also enables the "even before install" case: after a fresh clone you can
  run `python -m pytest -q` directly and the suite will find the package via src/.
- No production code is touched. No new dependencies (stdlib pathlib + sys only).
- Works for the lazy registry era: once the top-level `crap4code` package can be
  imported (python analyzer always available; JS/TS/Rust become lazy), the try
  succeeds even in "python-only" simulation environments that mock the grammar
  packages.

### How to use / verification (cross-shell)
From repo root (any shell):
    python -m pip install -e .[dev] && python -m pytest -q
    # or, even without the pip step on a fresh tree:
    python -m pytest -q

Targeted:
    python -m pytest tests/test_cli.py -q -k "cli or changed"

The guard is intentionally quiet; it only mutates sys.path when needed.

See also:
- WINDOWS_AND_CROSS_PLATFORM_PLAN.md (Dev1 + phase3-dx)
- pyproject.toml [tool.pytest.ini_options]
- AGENTS.md and README.md "Development" section (updated for the now-reliable command)

This file follows the project's "Teach Through Code" guideline: the durable
explanation lives here in the source so a future developer (or agent) can open
the file and understand the problem, the decision, the mechanism, and the
operational context without needing the chat history.
"""

from __future__ import annotations

import sys
from pathlib import Path


# --------------------------------------------------------------------------- #
# Cross-platform dev-experience import guard (Dev1 / phase3-dx)
# --------------------------------------------------------------------------- #
# Placed at module level so it executes as soon as pytest imports this conftest
# (which happens early in collection for the tests/ tree).
#
# Safe by construction:
# - Only mutates sys.path on ImportError (i.e. when the package is *not*
#   importable via the normal installed/editable/pythonpath mechanisms).
# - Uses an absolute path derived from this file's location so it works
#   regardless of cwd, PYTHONPATH contents, or which shell launched python.
# - Idempotent-ish: we check membership before insert (defensive).
# - Does not affect runtime behavior of the installed crap4code package
#   (users of `pip install crap4code` or the console script never load this).
# --------------------------------------------------------------------------- #

try:
    import crap4code  # succeeds if editable installed or pythonpath already did its job
except ImportError:
    # We are running "bare" from the source tree (pre-install, or editable
    # install did not surface the package for this python -m pytest invocation).
    # This situation was repeatedly observed on Windows pwsh/cmd due to the
    # interactions described in the module docstring.
    _here = Path(__file__).resolve()
    _repo_root = _here.parent.parent  # tests/conftest.py -> repo root
    _src_dir = _repo_root / "src"
    if _src_dir.is_dir():
        _src_str = str(_src_dir)
        if _src_str not in sys.path:
            # Prepend so that `import crap4code` and `from crap4code.xxx import ...`
            # succeed for all the test modules that are about to be imported by
            # pytest. Prepend (not append) to shadow any stale installed copy.
            sys.path.insert(0, _src_str)

    # We deliberately do *not* do a second `import crap4code` here.
    # If it still fails, the subsequent test module imports will produce a
    # clear traceback, which is the correct and debuggable failure mode.
    # The guard's only job is "make the obvious dev command work".
