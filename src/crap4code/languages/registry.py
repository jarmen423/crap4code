"""Canonical language registry used by the CLI."""

from __future__ import annotations

from crap4code.languages.base import LanguageDefinition
from crap4code.languages.javascript.analyzer import JavaScriptFamilyAnalyzer
from crap4code.languages.python.analyzer import PythonAnalyzer
from crap4code.languages.rust.analyzer import RustAnalyzer


def get_language_registry() -> dict[str, LanguageDefinition]:
    """Return the supported language registry for this build."""

    return {
        "python": LanguageDefinition(
            key="python",
            extensions=(".py",),
            analyzer=PythonAnalyzer(),
        ),
        "javascript": LanguageDefinition(
            key="javascript",
            extensions=(".js", ".jsx", ".mjs", ".cjs"),
            analyzer=JavaScriptFamilyAnalyzer(language="javascript"),
        ),
        "typescript": LanguageDefinition(
            key="typescript",
            extensions=(".ts", ".tsx"),
            analyzer=JavaScriptFamilyAnalyzer(language="typescript"),
        ),
        "rust": LanguageDefinition(
            key="rust",
            extensions=(".rs",),
            analyzer=RustAnalyzer(),
        ),
    }
