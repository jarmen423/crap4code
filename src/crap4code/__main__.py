"""Support for ``python -m crap4code``.

This module makes the top-level package executable as a module:

    python -m crap4code
    python -m crap4code --version
    python -m crap4code scan ...

It produces **identical behavior** to the console script defined in
``pyproject.toml``:

    [project.scripts]
    crap4code = "crap4code.main:main"

The delegation is intentionally thin and clean:

- ``__main__.py`` imports and calls ``main()`` from ``.main``
- ``main.py`` (the module targeted by the console script) delegates to
  ``cli.main``
- ``cli.py`` contains the real ``main(argv=None)`` argument parsing
  and command dispatch.

This pattern is the standard, idiomatic way for a package to support
both ``python -m pkg`` (cross-platform, no PATH issues) and the
generated ``pkg`` / ``pkg.exe`` entry point. It was missing, causing
``python -m crap4code`` to fail with "No module named crap4code.__main__"
(see Issue C1 in WINDOWS_AND_CROSS_PLATFORM_PLAN.md).

The ``if __name__ == "__main__":`` guard is retained for direct
execution of the file (rare) and for consistency with ``main.py``.

Do not add argument parsing, side effects, or imports of heavy
subsystems here. Keep this file a pure, minimal delegation point.
"""

from __future__ import annotations

from .main import main

if __name__ == "__main__":
    raise SystemExit(main())
