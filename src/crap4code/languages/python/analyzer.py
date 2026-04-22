"""Python analyzer using the standard library AST.

Python keeps the built-in parser because it is accurate, ubiquitous, and does
not require extra native grammar packages. The rest of the tool uses the same
stable per-function contract regardless of how each language discovers syntax.
"""

from __future__ import annotations

import ast
from pathlib import Path

from crap4code.core.coverage import normalize_repo_path
from crap4code.core.models import FunctionMetrics


_DECISION_NODES = (
    ast.If,
    ast.For,
    ast.AsyncFor,
    ast.While,
    ast.Try,
    ast.ExceptHandler,
    ast.With,
    ast.AsyncWith,
    ast.IfExp,
    ast.Match,
)


class _ComplexityCounter(ast.NodeVisitor):
    """Count branching inside one function without traversing nested functions."""

    def __init__(self, root: ast.AST) -> None:
        self.root = root
        self.complexity = 1

    def generic_visit(self, node: ast.AST) -> None:
        if node is not self.root and isinstance(
            node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)
        ):
            return

        if isinstance(node, _DECISION_NODES):
            self.complexity += 1

        if isinstance(node, ast.BoolOp):
            self.complexity += max(1, len(node.values) - 1)

        if isinstance(node, ast.comprehension):
            self.complexity += 1 + len(node.ifs)

        super().generic_visit(node)


def _compute_complexity(function_node: ast.AST) -> int:
    """Return complexity for a single function AST node."""

    counter = _ComplexityCounter(function_node)
    counter.visit(function_node)
    return counter.complexity


class _FunctionCollector(ast.NodeVisitor):
    """Collect Python function metrics while preserving class nesting."""

    def __init__(self, root: Path, file_path: Path) -> None:
        self.root = root
        self.file_path = file_path
        self._containers: list[str] = []
        self.metrics: list[FunctionMetrics] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._containers.append(node.name)
        self.generic_visit(node)
        self._containers.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._record_function(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._record_function(node)
        self.generic_visit(node)

    def _record_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        container = ".".join(self._containers) if self._containers else "module"
        self.metrics.append(
            FunctionMetrics(
                language="python",
                file_path=normalize_repo_path(self.file_path, self.root),
                container=container,
                function_name=node.name,
                start_line=node.lineno,
                end_line=getattr(node, "end_lineno", node.lineno),
                complexity=_compute_complexity(node),
            )
        )


class PythonAnalyzer:
    """Discover Python functions and complexity using ``ast``."""

    language = "python"
    extensions = (".py",)

    def analyze(self, root: Path, files: list[Path]) -> list[FunctionMetrics]:
        """Analyze Python files into the shared per-function contract."""

        results: list[FunctionMetrics] = []
        for file_path in files:
            try:
                source = file_path.read_text(encoding="utf-8")
                tree = ast.parse(source)
            except (OSError, SyntaxError, UnicodeDecodeError):
                continue

            collector = _FunctionCollector(root=root, file_path=file_path)
            collector.visit(tree)
            results.extend(collector.metrics)

        return results
