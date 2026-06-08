"""Canonical language registry used by the CLI.

This module implements the critical language decoupling (D1 + D3 / phase1-d1
from WINDOWS_AND_CROSS_PLATFORM_PLAN.md).

Python is *always* available because it uses only the stdlib ``ast`` module
(no native grammar packages; see python/analyzer.py docstring and its
_ComplexityCounter + NodeVisitor implementation).

The tree-sitter-backed languages are loaded *lazily and tolerantly*:

- The analyzer *class* imports (for javascript/analyzer.py which supplies both
  "javascript" and "typescript", and rust/analyzer.py) happen inside
  ``get_language_registry`` (wrapped in try/except).
- The actual grammar imports (``import tree_sitter_javascript`` etc. and
  ``from tree_sitter import ...``) have been moved *inside the analyzer
  __init__ methods* (see those files). This ensures the analyzer module can
  be imported (class obtained) without triggering a hard failure when the
  grammar wheel is absent.
- We only register a language (i.e. put its LanguageDefinition into the
  returned dict) if the analyzer class could be imported *and* an instance
  could be constructed successfully. Construction is what actually pulls the
  grammar at runtime.
- Consequence: ``import crap4code`` (or ``python -m crap4code scan`` for
  Python files) succeeds even if ``tree-sitter-rust`` (or the JS/TS grammars,
  or the core ``tree-sitter`` package) is completely uninstalled.
- The full 4-language experience continues to work when all the grammar
  packages are installed (as verified on this Windows box with the real
  .pyd wheels).

If a language is requested via the ``--lang`` CLI flag but is not present in
the runtime registry, the *CLI* (cli.py) emits a clear message of the form
"Rust support requires `pip install tree-sitter-rust`. Python and JS/TS will
still work." (or equivalent) and exits gracefully (no traceback, no fake
CRAP data). Unrequested missing languages are simply omitted from the
registry; callers that use the default (all enabled from config) see only
what is actually loadable.

This keeps recommendations deterministic/auditable and coverage
``indeterminate`` when data is absent. No top-level grammar imports remain
in the import graph for optional languages.

See also: base.py (the LanguageDefinition + Analyzer protocol), the per-lang
analyzer modules, cli.py:_scan (the --lang + selected_languages path and the
warning), core/config.py (load_project_config only sees languages that the
registry advertises), and the test suite (analyzer tests + test_cli + sample
projects still pass for available languages).
"""

from __future__ import annotations

from crap4code.languages.base import LanguageDefinition
from crap4code.languages.python.analyzer import PythonAnalyzer


def get_language_registry() -> dict[str, LanguageDefinition]:
    """Return the supported language registry for this build.

    Python entry is always present and constructed unconditionally (stdlib
    only; its import is at the top of this file).

    The three tree-sitter analyzer imports (JS family + Rust) are performed
    inside try/except blocks. A language is only entered in the returned dict
    when its analyzer class imported cleanly *and* the instance could be
    created (the instance creation is what executes the grammar imports that
    were moved inside the respective analyzer.__init__).

    Missing optional languages cause no ImportError at package import time
    and do not affect Python (or other languages whose grammars *are*
    loadable).
    """

    registry: dict[str, LanguageDefinition] = {
        # Python is unconditional and first. It must always load so that
        # `crap4code` remains usable for Python-only users or when any
        # tree-sitter grammar wheel is unavailable on the platform (Windows
        # wheel availability, corporate envs, arm64, future Python, etc.).
        "python": LanguageDefinition(
            key="python",
            extensions=(".py",),
            analyzer=PythonAnalyzer(),
        ),
    }

    # JavaScript and TypeScript share one analyzer implementation class but
    # load distinct grammars inside __init__. Register each language in its
    # own try/except so a missing TS grammar does not block JS (and vice versa).
    try:
        from crap4code.languages.javascript.analyzer import JavaScriptFamilyAnalyzer

        registry["javascript"] = LanguageDefinition(
            key="javascript",
            extensions=(".js", ".jsx", ".mjs", ".cjs"),
            analyzer=JavaScriptFamilyAnalyzer(language="javascript"),
        )
    except (ImportError, ModuleNotFoundError, AttributeError):
        # Missing tree-sitter-javascript (or core tree-sitter). CLI surfaces
        # a user-facing message only on explicit --lang javascript.
        pass

    try:
        from crap4code.languages.javascript.analyzer import JavaScriptFamilyAnalyzer

        registry["typescript"] = LanguageDefinition(
            key="typescript",
            extensions=(".ts", ".tsx"),
            analyzer=JavaScriptFamilyAnalyzer(language="typescript"),
        )
    except (ImportError, ModuleNotFoundError, AttributeError):
        # Missing tree-sitter-typescript (or core tree-sitter).
        pass

    # Rust is independent of the JS/TS grammars.
    try:
        from crap4code.languages.rust.analyzer import RustAnalyzer

        registry["rust"] = LanguageDefinition(
            key="rust",
            extensions=(".rs",),
            analyzer=RustAnalyzer(),
        )
    except (ImportError, ModuleNotFoundError, AttributeError):
        # Missing tree-sitter-rust (or core tree-sitter).  Python + JS/TS
        # (if their grammars loaded) continue to work.
        pass

    return registry
