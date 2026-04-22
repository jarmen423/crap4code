from __future__ import annotations

import ast
from pathlib import Path

from crap4code.core.files import discover_source_files
from crap4code.core.models import FunctionMetrics


class _ComplexityCounter(ast.NodeVisitor):
    def __init__(self, root: ast.AST) -> None:
        self.root = root
        self.complexity = 1

    def generic_visit(self, node: ast.AST) -> None:
        if node is not self.root and isinstance(
            node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        ):
            return

        if isinstance(
            node,
            (
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
            ),
        ):
            self.complexity += 1

        if isinstance(node, ast.BoolOp):
            self.complexity += max(1, len(node.values) - 1)

        if isinstance(node, ast.comprehension):
            self.complexity += 1 + len(node.ifs)

        super().generic_visit(node)


def _compute_complexity(function_node: ast.AST) -> int:
    counter = _ComplexityCounter(function_node)
    counter.visit(function_node)
    return counter.complexity


class _FunctionCollector(ast.NodeVisitor):
    def __init__(self, file_path: Path) -> None:
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
                file_path=self.file_path.as_posix(),
                container=container,
                function_name=node.name,
                line=node.lineno,
                complexity=_compute_complexity(node),
                coverage_percent=None,
                crap_score=None,
            )
        )


class PythonAnalyzer:
    language = "python"

    def discover_files(self, explicit_paths: list[str], changed_only: bool) -> list[Path]:
        return discover_source_files(
            explicit_paths, extensions=(".py",), changed_only=changed_only
        )

    def analyze(self, files: list[Path]) -> list[FunctionMetrics]:
        results: list[FunctionMetrics] = []
        for file_path in files:
            try:
                source = file_path.read_text(encoding="utf-8")
                tree = ast.parse(source)
            except (OSError, SyntaxError):
                continue

            collector = _FunctionCollector(file_path)
            collector.visit(tree)
            results.extend(collector.metrics)

        return results
